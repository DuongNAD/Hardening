#!/usr/bin/env python3
"""Hardening MCP server — bề mặt verifier cho agent.

Triết lý: model SINH, chương trình PHÁN.
Server này KHÔNG cho agent chạy shell tuỳ ý. Nó chỉ phơi ra một bộ động từ hữu
hạn, mỗi động từ chạy một lệnh cố định và trả về exit code thật. Agent không thể
tự chứng nhận, vì `verify` gọi thẳng scripts/verify.sh trong repo.

Chỉ dùng thư viện chuẩn — không cần pip install, không hỏng khi đổi máy.
Giao thức: JSON-RPC 2.0 trên stdio, mỗi message một dòng (MCP stdio transport).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

PROTOCOL = "2024-11-05"
SERVER = {"name": "hardening", "version": "1.0.0"}
TIMEOUT_DEFAULT = 900


# --------------------------------------------------------------- repo helpers
def _allowed_roots() -> list[Path]:
    raw = os.environ.get("HARDENING_ALLOWED_ROOTS", "")
    return [Path(p).expanduser().resolve() for p in raw.split(os.pathsep) if p.strip()]


def resolve_repo(repo: str | None) -> Path:
    """Chốt repo được phép thao tác. Mặc định lấy từ HARDENING_REPO."""
    cand = repo or os.environ.get("HARDENING_REPO") or os.getcwd()
    p = Path(cand).expanduser().resolve()
    if not p.is_dir():
        raise ValueError(f"khong phai thu muc: {p}")
    allowed = _allowed_roots()
    if allowed and not any(p == a or a in p.parents for a in allowed):
        raise ValueError(f"repo {p} nam ngoai HARDENING_ALLOWED_ROOTS")
    return p


def load_env(repo: Path) -> dict[str, str]:
    f = repo / ".hardening.env"
    if not f.exists():
        raise ValueError(
            f"{repo} chua duoc cai. Chay: hardening init {repo} --modules determinism,mutation"
        )
    env = {}
    for line in f.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def run(repo: Path, argv: list[str], timeout: int = TIMEOUT_DEFAULT) -> dict:
    try:
        r = subprocess.run(
            argv, cwd=repo, capture_output=True, text=True, timeout=timeout
        )
        out = (r.stdout or "") + (("\n[stderr]\n" + r.stderr) if r.stderr.strip() else "")
    except FileNotFoundError as e:
        return {"exit_code": 127, "output": f"khong tim thay lenh: {e}", "passed": False}
    except subprocess.TimeoutExpired:
        return {"exit_code": 124, "output": f"timeout sau {timeout}s", "passed": False}
    return {
        "exit_code": r.returncode,
        "output": out[-20000:],
        "passed": r.returncode == 0,
    }


def just(repo: Path, recipe: str, *args: str, timeout: int = TIMEOUT_DEFAULT) -> dict:
    return run(repo, ["just", recipe, *args], timeout=timeout)


# --------------------------------------------------------------------- tools
def t_detect(a: dict) -> dict:
    repo = resolve_repo(a.get("repo"))
    kit = Path(__file__).resolve().parent.parent / "hardening"
    r = run(repo, [str(kit), "detect", str(repo)], timeout=120)
    installed = (repo / ".hardening.env").exists()
    return {
        "repo": str(repo),
        "da_cai": installed,
        "chi_tiet": r["output"],
        "buoc_tiep": "san sang" if installed
        else f"chua cai — chay: hardening init {repo} --modules determinism,mutation",
    }


def t_status(a: dict) -> dict:
    repo = resolve_repo(a.get("repo"))
    env = load_env(repo)
    git = run(repo, ["git", "status", "--porcelain"], timeout=60)
    dirty = [l for l in git["output"].splitlines() if l.strip()]
    guard = f"{env.get('HD_CRATE','.')}/{env.get('HD_TEST','tests')}/".replace("./", "")
    outside = [l for l in dirty if guard not in l and "FINDINGS.md" not in l]
    return {
        "repo": str(repo),
        "ngon_ngu": env.get("HD_LANG"),
        "crate": env.get("HD_CRATE"),
        "vung_ghi_duy_nhat": guard,
        "modules": env.get("HD_MODULES"),
        "file_dang_sua": len(dirty),
        "vi_pham_pham_vi": outside or "khong",
        "canh_bao": "CO FILE NGOAI VUNG GHI — verify se tu choi" if outside else None,
    }


def t_baseline(a: dict) -> dict:
    repo = resolve_repo(a.get("repo"))
    load_env(repo)
    return just(repo, "baseline", timeout=3600)


def t_verify(a: dict) -> dict:
    """CỔNG. Đây là tool quan trọng nhất — không có nó thì cả server vô nghĩa."""
    repo = resolve_repo(a.get("repo"))
    load_env(repo)
    target = a.get("target", "")
    r = just(repo, "verify", target, timeout=a.get("timeout", 3600))
    r["passed"] = "QUA CONG" in r["output"] and r["exit_code"] == 0
    r["ket_luan"] = "QUA CONG — task xong" if r["passed"] else "CHUA XONG — doc output, sua test, thu lai (toi da 3 lan)"
    return r


def t_list_tasks(a: dict) -> dict:
    repo = resolve_repo(a.get("repo"))
    load_env(repo)
    r = just(repo, "list-missed", timeout=120)
    lines = [l.strip() for l in r["output"].splitlines() if l.strip() and (".rs:" in l or ".py:" in l)]
    limit = int(a.get("limit", 20))
    return {
        "tong": len(lines),
        "tasks": lines[:limit],
        "luat": "MOI DONG = MOT task cho MOT agent. Khong bao gio gop.",
    }


def t_hunt(a: dict) -> dict:
    repo = resolve_repo(a.get("repo"))
    load_env(repo)
    f = a.get("file")
    if f:
        return just(repo, "hunt-file", f, str(a.get("jobs", 6)), timeout=a.get("timeout", 7200))
    return just(repo, "hunt", str(a.get("shard", 1)), str(a.get("jobs", 6)),
                timeout=a.get("timeout", 7200))


def t_flaky(a: dict) -> dict:
    repo = resolve_repo(a.get("repo"))
    load_env(repo)
    n = str(a.get("runs", 20))
    r = just(repo, "flaky", n, timeout=a.get("timeout", 7200))
    r["ket_luan"] = ("cong Phase 0 DA MO — duoc sang mutation" if r["exit_code"] == 0
                     else "cong Phase 0 DONG — sua tat dinh truoc, dung chay mutation")
    return r


def t_seed_audit(a: dict) -> dict:
    repo = resolve_repo(a.get("repo"))
    load_env(repo)
    r = just(repo, "seed-audit", timeout=300)
    hits = [l for l in r["output"].splitlines() if ":" in l and "sach" not in l]
    return {"con_lai": len(hits), "vi_tri": hits[:50],
            "luat": "moi vi tri = MOT task cho skill determinism-fixer. Khong gop."}


def t_crashes(a: dict) -> dict:
    repo = resolve_repo(a.get("repo"))
    load_env(repo)
    return just(repo, "crashes", timeout=120)


def t_dataflow_verify(a: dict) -> dict:
    repo = resolve_repo(a.get("repo"))
    load_env(repo)
    r = just(repo, "dataflow-verify", timeout=1800)
    r["passed"] = "QUA CONG" in r["output"]
    return r


FINDING_TMPL = """
### {fid} — {title}
- **Ngày:** {date}
- **Loại:** {kind}
- **Vị trí:** `{location}`
- **Phát hiện bởi:** {found_by}
- **Triệu chứng:** {symptom}
- **Tái hiện:** `{repro}`
- **Test khoá lại:** `{test}`
- **Trạng thái:** OPEN
"""


def t_finding_add(a: dict) -> dict:
    """Ghi bug thật. Metric duy nhất đáng tin. Validate cứng để không nhận rác."""
    import datetime

    repo = resolve_repo(a.get("repo"))
    load_env(repo)
    kind = a.get("kind", "").upper()
    if kind not in {"BUG", "SMELL", "TEST-GAP"}:
        return {"passed": False, "loi": "kind phai la BUG | SMELL | TEST-GAP"}
    loc = a.get("location", "")
    if ":" not in loc:
        return {"passed": False, "loi": "location phai dang file:line"}
    if not a.get("repro"):
        return {"passed": False, "loi": "thieu lenh tai hien — khong tai hien duoc thi khong ghi"}

    f = repo / "FINDINGS.md"
    body = f.read_text() if f.exists() else "# FINDINGS\n"
    nxt = f"F-{sum(1 for l in body.splitlines() if l.startswith('### F-')):03d}"
    entry = FINDING_TMPL.format(
        fid=nxt, title=a.get("title", "(chua dat ten)"),
        date=datetime.date.today().isoformat(), kind=kind, location=loc,
        found_by=a.get("found_by", "khong ro"), symptom=a.get("symptom", ""),
        repro=a["repro"], test=a.get("test", "chua co"),
    )
    f.write_text(body.rstrip() + "\n" + entry)
    return {"passed": True, "id": nxt, "file": str(f)}


TOOLS = [
    ("hd_detect", "Nhan dien layout repo (ngon ngu, crate, src, tests) va so do nhanh. "
     "Goi dau tien khi chua biet repo trong the nao.",
     {"repo": ("string", "duong dan repo; bo trong = repo mac dinh")}, t_detect),
    ("hd_status", "Trang thai hien tai: modules da cai, vung ghi duy nhat, file dang sua, "
     "va CANH BAO neu dang sua file ngoai pham vi cho phep. Goi truoc khi bat dau sua.",
     {"repo": ("string", "duong dan repo")}, t_status),
    ("hd_baseline", "Chot so do goc (LOC, so test, RNG ban, coverage, mutation total). "
     "Chay MOT lan truoc moi thu. Khong co baseline thi khong danh gia duoc gi.",
     {"repo": ("string", "duong dan repo")}, t_baseline),
    ("hd_verify", "CONG DUY NHAT. Chay scripts/verify.sh: kiem pham vi ghi, cam #[ignore], "
     "cam xoa assertion, cam RNG phi tat dinh, chay test 3 lan, va bat mutant phai chet. "
     "Task CHI xong khi tool nay tra passed=true. Agent khong duoc tu tuyen bo hoan thanh.",
     {"repo": ("string", "duong dan repo"),
      "target": ("string", "nguyen dong mutant tu hd_list_tasks; bo trong cho task triage/dataflow")},
     t_verify),
    ("hd_list_tasks", "Danh sach mutant con song = danh sach task. Moi dong la MOT task cho "
     "MOT agent, khong bao gio gop.",
     {"repo": ("string", "duong dan repo"), "limit": ("integer", "so dong toi da, mac dinh 20")},
     t_list_tasks),
    ("hd_hunt", "Chay quet mutation de sinh danh sach mutant song. Ton CPU, khong ton token. "
     "Truyen 'file' de quet hep mot file (nen dung), hoac 'shard' 1..5 de chia sweep theo ngay.",
     {"repo": ("string", "duong dan repo"), "file": ("string", "quet hep mot file nguon"),
      "shard": ("integer", "1..5"), "jobs": ("integer", "so job song song, mac dinh 6")}, t_hunt),
    ("hd_flaky", "Cong ra Phase 0: chay toan bo test n lan lien tiep. Phai n/n pass moi duoc "
     "sang mutation. Suite flaky lam mutation testing sinh task rac.",
     {"repo": ("string", "duong dan repo"), "runs": ("integer", "so lan chay, mac dinh 20")},
     t_flaky),
    ("hd_seed_audit", "Liet ke moi nguon phi tat dinh con lai trong code nguon (RNG khong seed, "
     "wall-clock). Moi vi tri la mot task cho skill determinism-fixer.",
     {"repo": ("string", "duong dan repo")}, t_seed_audit),
    ("hd_crashes", "Liet ke crash artifact tu fuzzing chua duoc triage.",
     {"repo": ("string", "duong dan repo")}, t_crashes),
    ("hd_dataflow_verify", "Doi chieu dataflow.json (claim cua agent) voi do thi phu thuoc that. "
     "Edge bia -> fail. Edge bo sot -> fail. Invariant rong tuech -> fail.",
     {"repo": ("string", "duong dan repo")}, t_dataflow_verify),
    ("hd_finding_add", "Ghi mot bug that vao FINDINGS.md. Day la metric duy nhat that su quan "
     "trong. Bat buoc co location dang file:line va lenh tai hien, neu khong se bi tu choi.",
     {"repo": ("string", "duong dan repo"), "title": ("string", "tieu de mot dong"),
      "kind": ("string", "BUG | SMELL | TEST-GAP"), "location": ("string", "file:line"),
      "found_by": ("string", "mutant | fuzz | miri | determinism | dataflow | tay"),
      "symptom": ("string", "1-2 cau hanh vi sai the nao"),
      "repro": ("string", "lenh tai hien - BAT BUOC"),
      "test": ("string", "test khoa lai")}, t_finding_add),
]

HANDLERS = {name: fn for name, _, _, fn in TOOLS}


def tool_schema() -> list[dict]:
    out = []
    for name, desc, props, _ in TOOLS:
        schema = {
            "type": "object",
            "properties": {k: {"type": t, "description": d} for k, (t, d) in props.items()},
        }
        if name == "hd_finding_add":
            schema["required"] = ["kind", "location", "repro"]
        out.append({"name": name, "description": desc, "inputSchema": schema})
    return out


# ------------------------------------------------------------------ jsonrpc
def reply(rid, result=None, error=None):
    msg = {"jsonrpc": "2.0", "id": rid}
    msg["error" if error else "result"] = error or result
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def handle(req: dict):
    m, rid, params = req.get("method"), req.get("id"), req.get("params") or {}

    if m == "initialize":
        return reply(rid, {
            "protocolVersion": params.get("protocolVersion", PROTOCOL),
            "capabilities": {"tools": {}},
            "serverInfo": SERVER,
            "instructions": (
                "Bo cong verifier. Luat cung:\n"
                "1. Chi duoc ghi trong thu muc test — hd_status cho biet chinh xac o dau.\n"
                "2. Task CHI xong khi hd_verify tra passed=true. Khong tu tuyen bo hoan thanh.\n"
                "3. Moi dong tu hd_list_tasks la MOT task. Khong gop.\n"
                "4. Bi qua 3 lan thu -> dung, bao 'task qua lon, can chia nho'. Khong noi luat."
            ),
        })
    if m in ("notifications/initialized", "initialized"):
        return
    if m == "ping":
        return reply(rid, {})
    if m == "tools/list":
        return reply(rid, {"tools": tool_schema()})
    if m == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        fn = HANDLERS.get(name)
        if not fn:
            return reply(rid, error={"code": -32601, "message": f"khong co tool {name}"})
        try:
            res = fn(args)
        except Exception as e:  # noqa: BLE001 — trả lỗi cho agent thay vì chết
            res = {"passed": False, "loi": f"{type(e).__name__}: {e}"}
        text = json.dumps(res, ensure_ascii=False, indent=2)
        is_err = res.get("passed") is False or res.get("exit_code", 0) not in (0, None)
        return reply(rid, {"content": [{"type": "text", "text": text}], "isError": bool(is_err)})

    if rid is not None:
        reply(rid, error={"code": -32601, "message": f"method la: {m}"})


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            handle(json.loads(line))
        except json.JSONDecodeError:
            continue
        except BrokenPipeError:
            break


if __name__ == "__main__":
    main()
