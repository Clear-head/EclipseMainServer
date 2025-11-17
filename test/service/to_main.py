import asyncio
import time
from statistics import mean, stdev

from src.service.category.category_service import MainScreenService


async def measure_performance(method_name: str, iterations: int = 5):
    times = []

    for i in range(iterations):
        service = MainScreenService()  # 매번 새 인스턴스 생성

        start_time = time.perf_counter()  # time.time()보다 정확

        if method_name == "rg_to_main":
            await service.rg_to_main()
        elif method_name == "to_main":
            await service.to_main()
        elif method_name == "get_category_detail":
            await service.get_category_detail("ec468b63-be92-4718-b3b5-2145c1f939af")
        else:
            await service.rg_get_category_detail()

        elapsed = time.perf_counter() - start_time
        times.append(elapsed)
        print(f"{method_name} - Run {i + 1}: {elapsed:.4f}초")

    avg_time = mean(times)
    std_time = stdev(times) if len(times) > 1 else 0

    print(f"\n{method_name} 결과:")
    print(f"  평균: {avg_time:.4f}초")
    print(f"  표준편차: {std_time:.4f}초")
    print(f"  최소: {min(times):.4f}초")
    print(f"  최대: {max(times):.4f}초")

    return avg_time


async def main():
    print("=== 성능 측정 시작 ===\n")

    rg_avg = await measure_performance("rg_to_main", iterations=5)
    print("\n" + "=" * 50 + "\n")
    to_avg = await measure_performance("to_main", iterations=5)

    print("\n=== 비교 결과 ===")
    print(f"rg_to_main 평균: {rg_avg:.4f}초")
    print(f"to_main 평균: {to_avg:.4f}초")
    print(f"속도 차이: {abs(rg_avg - to_avg):.4f}초")

    if rg_avg < to_avg:
        improvement = ((to_avg - rg_avg) / to_avg) * 100
        print(f"rg_to_main이 {improvement:.1f}% 더 빠름")
    else:
        improvement = ((rg_avg - to_avg) / rg_avg) * 100
        print(f"to_main이 {improvement:.1f}% 더 빠름")


if __name__ == "__main__":
    asyncio.run(main())