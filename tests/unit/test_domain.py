import ast
from pathlib import Path
import unittest
from urllib.parse import quote

from codex_switch.domain.errors import SwitchError
from codex_switch.domain.models import UsageWindow
from codex_switch.domain.vless import parse_vless

LINK = "vless://00000000-0000-4000-8000-000000000001@example.com:443"


class DomainTests(unittest.TestCase):
    def test_ipv6_unicode_name_and_encoded_path(self):
        server = parse_vless(LINK.replace("example.com:443", "[::1]:8443") + "?type=ws&security=tls&path=%2Fws#" + quote("Рабочий"))
        self.assertEqual((server.host, server.port, server.name), ("::1", 8443, "Рабочий"))
        self.assertEqual(server.outbound["streamSettings"]["wsSettings"]["path"], "/ws")

    def test_identity_ignores_display_name_and_parameter_order(self):
        first = parse_vless(LINK + "?security=tls&type=tcp#First")
        other = parse_vless(LINK + "?type=tcp&security=tls#Second")
        self.assertEqual(first.id, other.id)

    def test_unsafe_or_unsupported_links_fail_without_credential_echo(self):
        cases = ["https://example.com", LINK + "?type=ws&type=tcp", LINK + "?security=reality",
                 LINK + "?allowInsecure=1", LINK + "?type=unknown", LINK + "?flow=xtls-rprx-vision&type=ws",
                 LINK + "?host=a%0d%0ab", LINK + "?encryption=custom", LINK + "?unknown=secret",
                 LINK.replace(":443", ":0"), LINK.replace(":443", ":99999")]
        for value in cases:
            with self.subTest(value=value), self.assertRaises(SwitchError) as exc:
                parse_vless(value)
            self.assertNotIn("00000000-", str(exc.exception))

    def test_reality_key_and_short_id_validation(self):
        valid = LINK + "?security=reality&pbk=" + "A" * 43 + "&sid=aabb&flow=xtls-rprx-vision"
        self.assertEqual(parse_vless(valid).security, "reality")
        for suffix in ("&sid=a", "&sid=zz"):
            with self.assertRaises(SwitchError):
                parse_vless(valid.split("&sid=")[0] + suffix)

    def test_usage_remaining_is_bounded(self):
        for used, expected in ((-10, 100), (0, 100), (26.5, 74), (100, 0), (110, 0)):
            self.assertEqual(UsageWindow(used, 300).remaining, expected)

    def test_model_repr_does_not_expose_credential(self):
        self.assertNotIn("00000000-0000", repr(parse_vless(LINK)))

    def test_architecture_dependencies_point_inward(self):
        root = Path(__file__).parents[2] / "src/codex_switch"
        forbidden = {
            "domain": ("os", "pathlib", "subprocess", "socket", "requests", "codex_switch.application", "codex_switch.infrastructure", "codex_switch.presentation"),
            "application": ("os", "pathlib", "subprocess", "socket", "codex_switch.infrastructure", "codex_switch.presentation"),
            "presentation": ("codex_switch.infrastructure",),
        }
        for layer, imports in forbidden.items():
            for path in (root / layer).glob("*.py"):
                tree = ast.parse(path.read_text())
                for node in ast.walk(tree):
                    modules = [n.name for n in node.names] if isinstance(node, ast.Import) else [node.module or ""] if isinstance(node, ast.ImportFrom) else []
                    for module in modules:
                        self.assertFalse(any(module == item or module.startswith(item + ".") for item in imports), f"{path.name}: {module}")
