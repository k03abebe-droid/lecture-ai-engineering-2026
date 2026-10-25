"""第1回 宿題（発展）: 応答時間とトークン数を、複数のモデル・質問で比較する。

使い方:
    uv run python scripts/bench_ask.py                      # 既定のモデル・質問で計測
    uv run python scripts/bench_ask.py -m gemini-2.5-flash -n 5 --sleep 6
    uv run python scripts/bench_ask.py --csv bench.csv      # 生データを CSV に保存

各呼び出しの応答時間（壁時計）と usage_metadata のトークン数を記録し、
モデル×質問ごとの平均を Markdown の表で出力する。
429（レート制限）などのエラーも記録して、計測を続ける。
"""

import argparse
import csv
import statistics
import sys
import time

from google import genai
from google.genai import errors

from app.config import get_api_key

DEFAULT_MODELS = [
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.8-flash",
]
DEFAULT_QUESTIONS = {
    "short": "日本の首都はどこですか？一言で答えてください。",
    "lora": "LoRAとは何ですか？",
    "course": "AIE2026の講座の宿題にある「3レベル」とは何ですか？",
}
FIELDS = [
    "model", "question", "run", "status", "latency_s",
    "prompt_tokens", "thoughts_tokens", "output_tokens", "total_tokens", "chars", "error",
]


def measure(client: genai.Client, model: str, question: str) -> dict:
    """1回呼び出して、応答時間とトークン数を返す。"""
    start = time.perf_counter()
    try:
        response = client.models.generate_content(model=model, contents=question)
    except errors.APIError as e:
        return {
            "status": e.code,
            "latency_s": round(time.perf_counter() - start, 3),
            "error": (e.message or "")[:300],
        }
    latency = time.perf_counter() - start
    usage = response.usage_metadata
    return {
        "status": 200,
        "latency_s": round(latency, 3),
        "prompt_tokens": usage.prompt_token_count or 0,
        "thoughts_tokens": usage.thoughts_token_count or 0,
        "output_tokens": usage.candidates_token_count or 0,
        "total_tokens": usage.total_token_count or 0,
        "chars": len(response.text or ""),
    }


def summarize(rows: list[dict]) -> str:
    """モデル×質問ごとの平均を Markdown の表にする。"""
    lines = [
        "| model | question | ok/n | 応答時間 平均[s] (min–max) | 入力 | 思考 | 出力 | 合計 | 出力tok/s |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    keys = dict.fromkeys((r["model"], r["question"]) for r in rows)
    for model, question in keys:
        group = [r for r in rows if r["model"] == model and r["question"] == question]
        ok = [r for r in group if r["status"] == 200]
        if not ok:
            codes = ",".join(sorted({str(r["status"]) for r in group}))
            lines.append(f"| {model} | {question} | 0/{len(group)} | エラー({codes}) | | | | | |")
            continue

        def mean(field: str) -> float:
            return statistics.mean(r[field] for r in ok)

        lat = [r["latency_s"] for r in ok]
        # 思考トークンも生成に時間がかかるので、出力+思考で速度を出す
        tps = statistics.mean((r["output_tokens"] + r["thoughts_tokens"]) / r["latency_s"] for r in ok)
        lines.append(
            f"| {model} | {question} | {len(ok)}/{len(group)} "
            f"| {mean('latency_s'):.2f} ({min(lat):.2f}–{max(lat):.2f}) "
            f"| {mean('prompt_tokens'):.0f} | {mean('thoughts_tokens'):.0f} "
            f"| {mean('output_tokens'):.0f} | {mean('total_tokens'):.0f} | {tps:.0f} |"
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="応答時間とトークン数を計測する")
    parser.add_argument("-m", "--models", nargs="+", default=DEFAULT_MODELS)
    parser.add_argument("-q", "--questions", nargs="+", choices=DEFAULT_QUESTIONS, default=list(DEFAULT_QUESTIONS))
    parser.add_argument("-n", "--runs", type=int, default=3, help="モデル×質問ごとの試行回数")
    parser.add_argument("--sleep", type=float, default=4.0, help="呼び出し間の待ち時間[秒]（RPM制限よけ）")
    parser.add_argument("--csv", help="生データを保存する CSV のパス")
    args = parser.parse_args()

    client = genai.Client(api_key=get_api_key())
    rows = []
    for model in args.models:
        for run in range(1, args.runs + 1):
            for name in args.questions:
                row = {"model": model, "question": name, "run": run}
                row |= measure(client, model, DEFAULT_QUESTIONS[name])
                rows.append(row)
                print(
                    f"{model:24} {name:7} #{run} status={row['status']} "
                    f"{row['latency_s']:6.2f}s total={row.get('total_tokens', '-')}",
                    file=sys.stderr,
                )
                time.sleep(args.sleep)

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
    print(summarize(rows))
    # 同じモデル・同じステータスのエラーは1回だけ表示する
    shown = set()
    for r in rows:
        if r["status"] != 200 and (r["model"], r["status"]) not in shown:
            shown.add((r["model"], r["status"]))
            print(f"\n[{r['model']} {r['question']} #{r['run']}] {r['status']}: {r['error']}")


if __name__ == "__main__":
    main()
