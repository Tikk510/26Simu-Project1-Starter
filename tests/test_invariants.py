import pytest
import os
import sys
import math

# 把 src 目录加进环境变量，让 pytest 找得到你的代码
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from simulator import V3PoolStateMachine

# V3 常数
Q96 = 2**96

@pytest.fixture
def pool():
    """创建测试池子"""
    # 初始价格 2500 USDC/ETH, sqrt_price ≈ 50
    initial_sqrt_price_x96 = int(math.sqrt(2500) * Q96)
    return V3PoolStateMachine(initial_sqrt_price_x96, 1000000)

def test_pool_initialization():
    """[红线 1] 池子必须正确初始化"""
    initial_sqrt_price_x96 = int(math.sqrt(2500) * Q96)
    pool = V3PoolStateMachine(initial_sqrt_price_x96, 1000000)

    assert pool.sqrtPriceX96 == initial_sqrt_price_x96
    assert pool.liquidity == 1000000
    assert pool.feeGrowthGlobal0X128 == 0
    assert pool.feeGrowthGlobal1X128 == 0

def test_zero_amount_swap_invariant():
    """[红线 2] 零输入交易不能改变池子状态"""
    pool = V3PoolStateMachine(int(math.sqrt(2500) * Q96), 1000000)

    initial_price = pool.sqrtPriceX96
    initial_liquidity = pool.liquidity

    # 尝试零输入swap
    result = pool.swap(zero_for_one=True, amount_specified=0, sqrt_price_limit_x96=pool.sqrtPriceX96)

    assert result['amount0'] == 0
    assert result['amount1'] == 0
    assert pool.sqrtPriceX96 == initial_price
    assert pool.liquidity == initial_liquidity

def test_negative_liquidity_impossible():
    """[红线 3] 流动性永远不能为负数"""
    pool = V3PoolStateMachine(int(math.sqrt(2500) * Q96), 1000000)

    # 添加正流动性
    pool.add_liquidity(-100, 100, 500000)

    # 验证流动性为正
    assert pool.liquidity >= 0

    # 即使在极端swap后也要为正
    pool.swap(zero_for_one=True, amount_specified=1000000, sqrt_price_limit_x96=int(math.sqrt(2000) * Q96))
    assert pool.liquidity >= 0

def test_price_bounds_respected():
    """[红线 4] 价格必须尊重上下限"""
    pool = V3PoolStateMachine(int(math.sqrt(2500) * Q96), 1000000)

    # 设置价格限制
    min_price_x96 = int(math.sqrt(2000) * Q96)
    max_price_x96 = int(math.sqrt(3000) * Q96)

    # 大额swap但限制价格
    pool.swap(zero_for_one=True, amount_specified=10000000, sqrt_price_limit_x96=min_price_x96)

    # 价格不能低于下限
    assert pool.sqrtPriceX96 >= min_price_x96

    # 反向swap
    pool.swap(zero_for_one=False, amount_specified=10000000, sqrt_price_limit_x96=max_price_x96)

    # 价格不能高于上限
    assert pool.sqrtPriceX96 <= max_price_x96

def test_invariant_preservation():
    """[红线 5] x * y = L^2 不变性必须保持（扣除手续费后）"""
    pool = V3PoolStateMachine(int(math.sqrt(2500) * Q96), 1000000)

    initial_invariant = pool.get_invariant()

    # 执行多个swap
    for _ in range(10):
        pool.swap(zero_for_one=True, amount_specified=100000, sqrt_price_limit_x96=int(math.sqrt(2000) * Q96))
        pool.swap(zero_for_one=False, amount_specified=100000, sqrt_price_limit_x96=int(math.sqrt(3000) * Q96))

    # 不变性应该大致保持（允许小幅偏差由于手续费）
    final_invariant = pool.get_invariant()
    deviation = abs(final_invariant - initial_invariant) / initial_invariant

    # 偏差应该小于1%（极端情况下）
    assert deviation < 0.01, f"Invariant violation: {deviation:.4f}"

def test_extreme_price_movement():
    """[红线 6] 极端价格变动下的系统稳定性"""
    pool = V3PoolStateMachine(int(math.sqrt(2500) * Q96), 1000000)

    # 添加流动性覆盖大范围
    pool.add_liquidity(-1000, 1000, 1000000)

    # 极端价格下跌
    crash_price_x96 = int(math.sqrt(100) * Q96)  # 价格从2500跌到100
    pool.swap(zero_for_one=True, amount_specified=10000000, sqrt_price_limit_x96=crash_price_x96)

    # 系统应该仍然稳定
    assert pool.liquidity >= 0
    assert pool.sqrtPriceX96 > 0

    # 价格反弹
    recovery_price_x96 = int(math.sqrt(5000) * Q96)
    pool.swap(zero_for_one=False, amount_specified=10000000, sqrt_price_limit_x96=recovery_price_x96)

    assert pool.liquidity >= 0
    assert pool.sqrtPriceX96 > 0

def test_liquidity_edge_cases():
    """[红线 7] 流动性临界情况测试"""
    pool = V3PoolStateMachine(int(math.sqrt(2500) * Q96), 0)  # 从零流动性开始

    # 添加流动性到不同区间
    pool.add_liquidity(-100, 0, 500000)
    pool.add_liquidity(0, 100, 500000)

    # 当前价格在区间内
    current_tick = pool._get_tick_from_price()
    assert -100 <= current_tick < 100

    # 流动性应该正确累积
    assert pool.liquidity > 0

def test_tick_crossing_integrity():
    """[红线 8] Tick穿越时的完整性"""
    pool = V3PoolStateMachine(int(math.sqrt(2500) * Q96), 1000000)

    # 添加流动性跨越多个tick
    for i in range(-5, 6):
        pool.add_liquidity(i*10, (i+1)*10, 100000)

    initial_liquidity = pool.liquidity

    # 执行大额swap，穿越多个tick
    pool.swap(zero_for_one=True, amount_specified=5000000, sqrt_price_limit_x96=int(math.sqrt(2000) * Q96))

    # 流动性应该仍然合理
    assert pool.liquidity >= 0
    assert pool.liquidity <= initial_liquidity * 2  # 不会无限制增长

def test_mathematical_consistency():
    """[红线 9] 数学一致性检查"""
    pool = V3PoolStateMachine(int(math.sqrt(2500) * Q96), 1000000)

    # 检查价格计算的一致性
    price_from_sqrt = pool.get_current_price()
    expected_price = 2500.0

    # 允许小幅误差（由于定点数精度）
    assert abs(price_from_sqrt - expected_price) / expected_price < 0.01

def test_system_death_by_liquidity_drain():
    """[红线 10] 流动性耗尽导致的系统死亡"""
    pool = V3PoolStateMachine(int(math.sqrt(2500) * Q96), 1000000)

    # 添加少量流动性
    pool.add_liquidity(-10, 10, 1000)

    # 大额swap耗尽流动性
    try:
        pool.swap(zero_for_one=True, amount_specified=10000000, sqrt_price_limit_x96=int(math.sqrt(2000) * Q96))
        # 如果没有崩溃，检查流动性是否被正确处理
        assert pool.liquidity >= 0
    except Exception as e:
        # 如果系统崩溃，这是预期的行为
        pytest.fail(f"系统在流动性耗尽时崩溃: {e}")

def test_rounding_error_accumulation():
    """[红线 11] 舍入误差累积测试"""
    pool = V3PoolStateMachine(int(math.sqrt(2500) * Q96), 1000000)

    # 执行大量小额交易
    for i in range(100):
        pool.swap(zero_for_one=True, amount_specified=1000, sqrt_price_limit_x96=int(math.sqrt(2400) * Q96))
        pool.swap(zero_for_one=False, amount_specified=1000, sqrt_price_limit_x96=int(math.sqrt(2600) * Q96))

    # 系统应该仍然稳定
    assert pool.liquidity >= 0
    assert pool.sqrtPriceX96 > 0

    # 不变性应该大致保持
    invariant = pool.get_invariant()
    assert invariant > 0