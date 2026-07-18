"""Compare one-shot CLI and resident-server barcode generation throughput."""

from __future__ import annotations

import argparse
import math
import os
import platform
import statistics
import time
from collections.abc import Callable, Sequence
from pathlib import Path

from barcodekit import BarcodeKit


def _percentile(values: Sequence[float], percentile: float) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * percentile) - 1)
    return ordered[index]


def _measure(action: Callable[[], None], rounds: int) -> list[float]:
    durations: list[float] = []
    for _ in range(rounds):
        started = time.perf_counter()
        action()
        durations.append(time.perf_counter() - started)
    return durations


def _options(symbology: str, size: int) -> dict[str, object]:
    options: dict[str, object] = {"size": size}
    if symbology == "qr":
        options["level"] = "M"
    return options


def _print_result(
    mode: str,
    workers: str,
    durations: Sequence[float],
    count: int,
) -> None:
    median = statistics.median(durations)
    p95 = _percentile(durations, 0.95)
    throughput = count / median
    print(
        f"{mode:<10} {workers:>7} {median * 1000:>12.2f} "
        f"{p95 * 1000:>10.2f} {throughput:>14.1f}"
    )


def benchmark(arguments: argparse.Namespace) -> None:
    texts = [f"BARCODEKIT-BENCH-{index:08d}" for index in range(arguments.count)]
    options = _options(arguments.symbology, arguments.size)
    executable = arguments.executable

    print(f"Platform: {platform.platform()}")
    print(f"Python:   {platform.python_version()}")
    print(f"CPUs:     {os.cpu_count() or 'unknown'}")
    print(f"Barcode:  {arguments.symbology}, size={arguments.size}, count={arguments.count}")
    print()
    print(f"{'Mode':<10} {'Workers':>7} {'Median ms':>12} {'p95 ms':>10} {'Images/sec':>14}")
    print("-" * 59)

    if not arguments.skip_cli:
        cli = BarcodeKit(executable=executable, timeout=arguments.timeout)
        for text in texts[: arguments.warmup]:
            cli.generate(arguments.symbology, text, **options)
        cli_durations = _measure(
            lambda: [cli.generate(arguments.symbology, text, **options) for text in texts],
            arguments.rounds,
        )
        _print_result("CLI", "1", cli_durations, arguments.count)

    for workers in dict.fromkeys(arguments.workers):
        with BarcodeKit(
            executable=executable,
            timeout=arguments.timeout,
            server=True,
        ) as kit:
            for text in texts[: arguments.warmup]:
                kit.generate(arguments.symbology, text, **options)

            def generate_batch(worker_count: int = workers) -> None:
                kit.generate_many(
                    arguments.symbology,
                    texts,
                    workers=worker_count,
                    **options,
                )

            durations = _measure(
                generate_batch,
                arguments.rounds,
            )
        _print_result("Server", str(workers), durations, arguments.count)


def _positive_int(value: str) -> int:
    integer = int(value)
    if integer < 1:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return integer


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path)
    parser.add_argument("--symbology", choices=("datamatrix", "qr"), default="datamatrix")
    parser.add_argument("--size", type=_positive_int, default=256)
    parser.add_argument("--count", type=_positive_int, default=200)
    parser.add_argument("--rounds", type=_positive_int, default=5)
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument("--workers", type=_positive_int, nargs="+", default=[1, 2, 4, 8])
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--skip-cli", action="store_true")
    arguments = parser.parse_args()
    if arguments.warmup < 0:
        parser.error("--warmup must be zero or greater")
    if not math.isfinite(arguments.timeout) or arguments.timeout <= 0:
        parser.error("--timeout must be a finite number greater than zero")
    benchmark(arguments)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
