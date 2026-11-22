"""Claude komut satırı üzerinden temiz bağlamla model çağrısı."""
import json
import os
import subprocess
from tempfile import TemporaryDirectory

OPUS = "claude-opus-5-5"
SONNET = "claude-sonnet-5-5"
# Sunucunun model ve efor standardı (20.11.2026): her çağrı eforu açık yazar. --setting-sources "" ayar
# dosyasını okutmaz; --effort verilmezse model kendi varsayılanıyla çalışır (20.11.2026 öncesi ölçümler böyleydi).
EFOR = "xhigh"


class ModelHatasi(RuntimeError):
    """Claude çağrısı tamamlanamadı."""


def claude_komut(model, effort=EFOR):
    return ["claude", "-p", "--output-format", "json", "--setting-sources", "", "--tools", "",
            "--strict-mcp-config", "--no-session-persistence", "--effort", effort, "--model", model]


def claude_ortam():
    ortam = {k: v for k, v in os.environ.items() if not k.upper().startswith(("CLAUDE", "ANTHROPIC"))}
    ortam.update(CLAUDE_CODE_DISABLE_CLAUDE_MDS="1", CLAUDE_CODE_DISABLE_AUTO_MEMORY="1")
    return ortam


def claude_sonuc(stdout):
    try:
        kayit = json.loads(stdout)
    except ValueError as e:
        raise ModelHatasi("claude çıktısı JSON değil") from e
    if not isinstance(kayit, dict):
        raise ModelHatasi("claude çıktısı JSON nesnesi değil")
    if kayit.get("type") != "result" or kayit.get("subtype") != "success" or kayit.get("is_error") is not False:
        raise ModelHatasi(f"claude sonucu başarısız: {kayit.get('subtype')} {str(kayit.get('result'))[:200]}")
    if kayit.get("stop_reason") != "end_turn":
        raise ModelHatasi(f"claude yarım kaldı: {kayit.get('stop_reason')}")
    metin = kayit.get("result") or ""
    if not isinstance(metin, str):
        raise ModelHatasi("claude sonucu metin değil")
    return metin.strip()


def claude(model):
    """İstemi standart girdiden alan bir model çağrısı döndür."""
    def cagir(istem):
        with TemporaryDirectory() as bos:
            r = subprocess.run(claude_komut(model), input=istem, cwd=bos, env=claude_ortam(),
                               capture_output=True, text=True, timeout=900)
        if r.returncode != 0:
            raise ModelHatasi(f"claude çıkış kodu {r.returncode}: {(r.stderr or r.stdout)[-500:]}")
        return claude_sonuc(r.stdout)
    return cagir
