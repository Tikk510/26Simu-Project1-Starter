import os
import sys
import math
import pandas as pd
import yaml

print("🚀 [System] 启动 Project 1：V3 状态机极限压测台...")

# 读取配置
with open('../spec.yaml', 'r') as f:
    config = yaml.safe_load(f)

print(f"📊 [Config] 加载配置: {config['model']['name']} by {config['model']['author']}")

# 添加 src 到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from simulator import V3PoolStateMachine

# V3 常数
Q96 = 2**96

def run_price_stress_test():
    """运行价格压力测试"""
    print("🔥 [StressTest] 开始价格极限测试...")

    # 初始化池子
    initial_sqrt_price_x96 = int(math.sqrt(config['pool']['initial_price']) * Q96)
    initial_liquidity = int(config['pool']['initial_liquidity'])

    pool = V3PoolStateMachine(initial_sqrt_price_x96, initial_liquidity)

    # 添加基础流动性
    pool.add_liquidity(-1000, 1000, initial_liquidity // 10)

    results = []

    # 测试不同价格水平的滑点
    test_prices = [500, 1000, 1500, 2000, 2500, 3000, 4000, 5000]
    swap_amounts = [10000, 50000, 100000, 500000, 1000000]

    for target_price in test_prices:
        target_sqrt_price_x96 = int(math.sqrt(target_price) * Q96)

        for amount in swap_amounts:
            # 重置池子状态
            pool.sqrtPriceX96 = initial_sqrt_price_x96
            pool.liquidity = initial_liquidity

            # 执行swap
            zero_for_one = target_price < config['pool']['initial_price']
            result = pool.swap(zero_for_one, amount, target_sqrt_price_x96)

            # 计算实际执行价格和滑点
            actual_price = pool.get_current_price()
            slippage = abs(actual_price - target_price) / target_price * 100

            results.append({
                'target_price': target_price,
                'swap_amount': amount,
                'actual_price': actual_price,
                'slippage_percent': slippage,
                'amount0': result['amount0'],
                'amount1': result['amount1'],
                'fee_amount': result['fee_amount'],
                'final_liquidity': pool.liquidity
            })

            print(f"  💰 Swap {amount} -> Price: {target_price} -> {actual_price:.2f}, Slippage: {slippage:.2f}%")

    return results

def run_liquidity_drain_test():
    """运行流动性耗尽测试"""
    print("🌊 [LiquidityTest] 开始流动性耗尽测试...")

    initial_sqrt_price_x96 = int(math.sqrt(config['pool']['initial_price']) * Q96)
    pool = V3PoolStateMachine(initial_sqrt_price_x96, 1000000)

    # 添加有限流动性
    pool.add_liquidity(-10, 10, 100000)  # 很窄的区间

    results = []
    total_swapped = 0

    # 逐渐增加swap数量直到流动性耗尽
    for i in range(100):
        amount = 10000 * (i + 1)

        try:
            result = pool.swap(True, amount, int(math.sqrt(2000) * Q96))
            total_swapped += amount

            results.append({
                'step': i,
                'swap_amount': amount,
                'total_swapped': total_swapped,
                'liquidity_remaining': pool.liquidity,
                'price': pool.get_current_price(),
                'success': True
            })

            if pool.liquidity == 0:
                print(f"  💥 流动性耗尽 at step {i}, total swapped: {total_swapped}")
                break

        except Exception as e:
            results.append({
                'step': i,
                'swap_amount': amount,
                'total_swapped': total_swapped,
                'liquidity_remaining': pool.liquidity,
                'price': pool.get_current_price(),
                'success': False,
                'error': str(e)
            })
            print(f"  ❌ 错误 at step {i}: {e}")
            break

    return results

def run_invariant_test():
    """运行不变性测试"""
    print("⚖️ [InvariantTest] 开始不变性验证...")

    initial_sqrt_price_x96 = int(math.sqrt(config['pool']['initial_price']) * Q96)
    pool = V3PoolStateMachine(initial_sqrt_price_x96, 1000000)

    results = []
    initial_invariant = pool.get_invariant()

    # 执行一系列swap
    for i in range(50):
        # 随机方向和数量
        zero_for_one = (i % 2) == 0
        amount = 10000 + (i * 1000)

        price_limit = int(math.sqrt(2000 if zero_for_one else 3000) * Q96)
        pool.swap(zero_for_one, amount, price_limit)

        current_invariant = pool.get_invariant()
        deviation = abs(current_invariant - initial_invariant) / initial_invariant * 100

        results.append({
            'step': i,
            'invariant': current_invariant,
            'deviation_percent': deviation,
            'price': pool.get_current_price(),
            'liquidity': pool.liquidity
        })

        if i % 10 == 0:
            print(f"  📏 Step {i}: Invariant deviation: {deviation:.4f}%")

    return results

def main():
    """主函数"""
    # 创建results目录
    os.makedirs('../results', exist_ok=True)

    # 运行所有测试
    print("\n" + "="*60)
    print("🧪 执行极限压测...")
    print("="*60)

    # 1. 价格压力测试
    price_results = run_price_stress_test()

    # 2. 流动性耗尽测试
    liquidity_results = run_liquidity_drain_test()

    # 3. 不变性测试
    invariant_results = run_invariant_test()

    # 保存结果
    print("\n💾 [Save] 保存测试结果...")

    # 价格测试结果
    price_df = pd.DataFrame(price_results)
    price_df.to_csv('../results/price_stress_test.csv', index=False)

    # 流动性测试结果
    liquidity_df = pd.DataFrame(liquidity_results)
    liquidity_df.to_csv('../results/liquidity_drain_test.csv', index=False)

    # 不变性测试结果
    invariant_df = pd.DataFrame(invariant_results)
    invariant_df.to_csv('../results/invariant_test.csv', index=False)

    # 生成汇总metrics
    metrics = {
        'max_slippage_percent': price_df['slippage_percent'].max(),
        'avg_slippage_percent': price_df['slippage_percent'].mean(),
        'liquidity_drain_threshold': liquidity_df[liquidity_df['liquidity_remaining'] == 0]['total_swapped'].iloc[0] if len(liquidity_df[liquidity_df['liquidity_remaining'] == 0]) > 0 else None,
        'max_invariant_deviation_percent': invariant_df['deviation_percent'].max(),
        'final_invariant_deviation_percent': invariant_df['deviation_percent'].iloc[-1],
        'test_completed': True
    }

    # 保存metrics
    with open('../results/metrics.json', 'w') as f:
        import json
        json.dump(metrics, f, indent=2)

    print("✅ [Status] 流水线运行完毕")
    print("📊 [Results] 结果已保存到 results/ 目录")
    print(f"   - price_stress_test.csv: {len(price_results)} 条记录")
    print(f"   - liquidity_drain_test.csv: {len(liquidity_results)} 条记录")
    print(f"   - invariant_test.csv: {len(invariant_results)} 条记录")
    print("   - metrics.json: 汇总指标"

if __name__ == "__main__":
    main()
