import io, json, os, tempfile, unittest
from contextlib import redirect_stdout
from pathlib import Path

from terzi import kanca

YZ = ("Bu yöntem verimliliği artırmaktadır. Ayrıca maliyetleri düşürmektedir. Kullanıcılar da memnun kalmaktadır. "
      "Şirket bu çalışmayla önemli bir adım atmaktadır ve sektörde öncü bir konuma gelmektedir. Ekip de yeni "
      "projeler geliştirmektedir. Yönetim bu süreci yakından izlemektedir — çalışanlara da destek vermektedir.")


class Kanca(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        os.environ["XDG_STATE_HOME"] = self.d.name

    def tearDown(self):
        self.d.cleanup()

    def calistir(self, kip, girdi):
        import sys
        eski = sys.stdin
        sys.stdin = io.StringIO(json.dumps(girdi))
        out = io.StringIO()
        try:
            with redirect_stdout(out):
                kanca.main([kip])
        finally:
            sys.stdin = eski
        return out.getvalue().strip()

    def test_turkce_dosyada_bir_kez_uyarir(self):
        p = Path(self.d.name) / "yazi.md"
        p.write_text(YZ, encoding="utf-8")
        girdi = {"session_id": "s1", "tool_name": "Write", "tool_input": {"file_path": str(p)}}
        ilk = self.calistir("yazim", girdi)
        self.assertEqual(json.loads(ilk)["decision"], "block")
        self.assertIn("uzun tire", ilk)  # B001 bulgusu metne girdi
        self.assertEqual(self.calistir("yazim", girdi), "")  # ikinci kez susar

    def test_kod_ve_ingilizce_dosyada_sessiz(self):
        p = Path(self.d.name) / "a.py"
        p.write_text(YZ, encoding="utf-8")
        self.assertEqual(self.calistir("yazim", {"tool_input": {"file_path": str(p)}}), "")
        q = Path(self.d.name) / "b.md"
        q.write_text("This is an English text. " * 40, encoding="utf-8")
        self.assertEqual(self.calistir("yazim", {"tool_input": {"file_path": str(q)}}), "")

    def test_bozuk_girdide_sessiz(self):
        import sys
        eski = sys.stdin
        sys.stdin = io.StringIO("{bozuk")
        try:
            self.assertEqual(kanca.main(["yazim"]), 0)
        finally:
            sys.stdin = eski

    def test_stop_kancasi_dongu_yapmaz(self):
        self.assertEqual(self.calistir("yanit", {"stop_hook_active": True, "transcript_path": "/yok"}), "")
