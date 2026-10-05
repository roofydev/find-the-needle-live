"""GH #104 supporter privacy: python -m unittest discover -s Tools/Community/tests -v"""

import importlib.util
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("patreon_sync", HERE.parent / "patreon_sync.py")
ps = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ps)

TIERS = {"seedling": 1, "farmhand": 2, "golden needle": 3}


def member(mid, status="active_patron", tiers=("t1",), name="Legal Name", email="x@example.com"):
    return {"id": mid, "type": "member",
            "attributes": {"patron_status": status, "full_name": name, "email": email, "currently_entitled_amount_cents": 700},
            "relationships": {"currently_entitled_tiers": {"data": [{"id": t, "type": "tier"} for t in tiers]}}}


INCLUDED = [
    {"id": "t1", "type": "tier", "attributes": {"title": "Seedling", "amount_cents": 300}},
    {"id": "t2", "type": "tier", "attributes": {"title": "Farmhand", "amount_cents": 700}},
    {"id": "t3", "type": "tier", "attributes": {"title": "Golden Needle", "amount_cents": 1500}},
    {"id": "tx", "type": "tier", "attributes": {"title": "Mystery Tier", "amount_cents": 500}},
    {"id": "tf", "type": "tier", "attributes": {"title": "Free", "amount_cents": 0}},
]


def page(*members):
    return {"data": list(members), "included": INCLUDED, "links": {}}


def aliases(**entries):
    return json.dumps({"version": 1, "members": entries})


class AliasMapTests(unittest.TestCase):
    def test_empty_map_means_nobody(self):
        self.assertEqual(ps.parse_alias_map(None), {})
        self.assertEqual(ps.parse_alias_map("  "), {})

    def test_only_explicit_true_consent_counts(self):
        raw = aliases(a={"alias": "Ann", "consent": True}, b={"alias": "Bob", "consent": "yes"},
                      c={"alias": "Cy"}, d={"alias": "Di", "consent": False})
        self.assertEqual(ps.parse_alias_map(raw), {"a": "Ann"})

    def test_malformed_maps_are_rejected(self):
        for raw in ['{"version":1,"members":', '[]', '{"members":{}}', '{"version":2,"members":{}}',
                    '{"version":1,"members":[]}', '{"version":1,"members":{"a":"Ann"}}']:
            with self.assertRaises(ps.AliasMapError, msg=raw):
                ps.parse_alias_map(raw)

    def test_alias_sanitizing(self):
        self.assertEqual(ps.clean_alias("<b>Ann</b>"), "bAnn/b")
        self.assertEqual(ps.clean_alias("A​n\u0000n\n"), "Ann")
        self.assertEqual(ps.clean_alias("  Roofy․  "), "Roofy․")
        self.assertEqual(len(ps.clean_alias("x" * 100)), ps.MAX_ALIAS)
        self.assertEqual(ps.clean_alias(42), "")
        self.assertEqual(ps.parse_alias_map(aliases(a={"alias": "<>", "consent": True})), {})


class BuildTests(unittest.TestCase):
    def test_opted_in_members_get_alias_and_tier_only(self):
        out = ps.build_supporters([page(member("a", tiers=("t3",)), member("b", tiers=("t1", "t2")))], TIERS,
                                  {"a": "GoldFan", "b": "Helper"})
        self.assertEqual(out, [{"name": "GoldFan", "tier": 3}, {"name": "Helper", "tier": 2}])
        blob = json.dumps(out)
        for leak in ("Legal Name", "example.com", '"a"', "700", "member"):
            self.assertNotIn(leak, blob)

    def test_no_consent_is_never_listed(self):
        self.assertEqual(ps.build_supporters([page(member("a"), member("b"))], TIERS, {}), [])
        self.assertEqual(ps.build_supporters([page(member("a"))], TIERS, {"zzz": "Other"}), [])

    def test_inactive_and_free_members_are_hidden(self):
        pages = [page(member("a", status="former_patron"), member("b", status="declined_patron"),
                      member("c", status=None), member("d", tiers=("tf",)), member("e", tiers=()))]
        al = {k: k.upper() for k in "abcde"}
        self.assertEqual(ps.build_supporters(pages, TIERS, al), [])

    def test_unknown_paid_tier_counts_as_seedling(self):
        self.assertEqual(ps.build_supporters([page(member("a", tiers=("tx",)))], TIERS, {"a": "Ann"}), [{"name": "Ann", "tier": 1}])

    def test_malformed_pages_are_skipped(self):
        bad = [None, "x", {"data": None}, {"data": ["x", {"id": "a"}, {"id": "a", "attributes": "?"}]},
               {"data": [{"id": "a", "attributes": {"patron_status": "active_patron"}, "relationships": {"currently_entitled_tiers": {"data": "?"}}}]},
               {"data": [member("a", tiers=("missing",))], "included": [{"type": "tier"}, "junk"]}]
        self.assertEqual(ps.build_supporters(bad, TIERS, {"a": "Ann"}), [])

    def test_list_is_capped(self):
        ids = [f"m{i}" for i in range(200)]
        out = ps.build_supporters([page(*[member(i) for i in ids])], TIERS, {i: i for i in ids})
        self.assertEqual(len(out), ps.MAX_SUPPORTERS)


class MainTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        (self.dir / "patreon.json").write_text(json.dumps({"tiers": [{"id": 1, "name": "Seedling"}, {"id": 2, "name": "Farmhand"}, {"id": 3, "name": "Golden Needle"}]}))
        self.out = self.dir / "supporters.json"
        self.out.write_text('{"supporters": [{"name": "Keep", "tier": 1}]}')

    def run_main(self, env, pages):
        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(ps, "fetch_pages", return_value=pages):
            so, se = io.StringIO(), io.StringIO()
            with redirect_stdout(so), redirect_stderr(se):
                code = ps.main(["--root", str(self.dir)])
        return code, so.getvalue() + se.getvalue()

    def test_bad_alias_secret_fails_closed_without_writing(self):
        code, log = self.run_main({"PATREON_CREATOR_TOKEN": "t", "SUPPORTER_ALIASES": "{broken"}, [page(member("a"))])
        self.assertEqual(code, 2)
        self.assertIn("Keep", self.out.read_text())
        self.assertNotIn("{broken", log)

    def test_logs_hold_counts_only(self):
        code, log = self.run_main({"PATREON_CREATOR_TOKEN": "t", "SUPPORTER_ALIASES": aliases(secretid={"alias": "Ann", "consent": True})},
                                  [page(member("secretid"), member("other"))])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(self.out.read_text())["supporters"], [{"name": "Ann", "tier": 1}])
        for leak in ("secretid", "other", "Legal Name", "Ann"):
            self.assertNotIn(leak, log)

    def test_missing_token_skips(self):
        code, _ = self.run_main({}, [])
        self.assertEqual(code, 0)
        self.assertIn("Keep", self.out.read_text())


if __name__ == "__main__":
    unittest.main()
