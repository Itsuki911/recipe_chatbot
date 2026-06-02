from __future__ import annotations

import platform
import traceback
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

try:
    from app.config import ERROR_LOG_PATH
except ImportError:
    # configのimport自体が壊れている場合でも、最低限ログを書けるようにします。
    ERROR_LOG_PATH = Path(__file__).resolve().parent.parent / "ERROR_LOG.md"


def _now_jst() -> str:
    # ユーザーの作業時間に合わせて、日本時間でログを残します。
    return datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y-%m-%d %H:%M:%S %Z")


def ensure_error_log(path: Path = ERROR_LOG_PATH) -> None:
    # 初回だけログファイルを作成します。既にあるログは上書きしません。
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Error Log\n\n"
        "このファイルは開発中に発生したエラーをCodexが後から確認するためのログです。\n"
        "新しいエラーはアプリ側の例外処理から自動追記されます。\n\n",
        encoding="utf-8",
    )


def log_error(context: str, error: BaseException, details: str | None = None) -> None:
    try:
        ensure_error_log()
        # 後から原因を追いやすいように、発生場所・例外型・Python版・tracebackをまとめます。
        entry = [
            f"## {_now_jst()}",
            "",
            f"- Context: {context}",
            f"- Error Type: {type(error).__name__}",
            f"- Message: {error}",
            f"- Python: {platform.python_version()}",
        ]
        if details:
            entry.extend(["", "### Details", "", "```text", details.strip(), "```"])
        entry.extend(["", "### Traceback", "", "```text", "".join(traceback.format_exception(error)).strip(), "```", ""])
        with ERROR_LOG_PATH.open("a", encoding="utf-8") as file:
            file.write("\n".join(entry))
    except Exception:
        # Error logging must never break the user-facing app flow.
        return
