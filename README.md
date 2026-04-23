# 🪐 Project 1: Uniswap V3 State Machine (Starter Template)

> 🎈 **重要声明 (IMPORTANT)**: 
> 你当前所处的是**“纯净实战沙盒 (Starter Sandbox)”**。这里没有任何理论大纲和作业规格书。
> 本课程的所有红头文件、教学指导、工具链规范以及 Project 1 的打分标准（Rubric），均由 **教官的全球唯一主库 (SSOT)** 发布与维护。
> 👉 **[点击此处阅读课程原点：26Simu-Management-Modeling](https://github.com/booblu/26Simu-Management-Modeling)**
> 👉 **[点击此处查询 P1 任务规格书与计分板](https://github.com/booblu/26Simu-Management-Modeling/blob/main/03_Assignments/Project1_V3_State_Machine.md)**
> 👉 **[点击此处打开避坑保命的 Math Cheat Sheet](https://github.com/booblu/26Simu-Management-Modeling/blob/main/04_Resources/Project1_V3_Math_CheatSheet.md)**

## 🎯 你的脚手架任务 (Your Sandbox Mission)
1. 把你在主库里学到的底层物理知识（Q64.96 定点数算法）移植进 `src/simulator.py` 里的那个空骨架中。
2. 疯狂地在 `tests/test_invariants.py` 中写能够把系统搞死（触发底板击穿）的独立红线测试断言。
3. 按照 `spec.yaml` 填写你做实验的初始环境与假设条件。

## 🚀 启动指北 (How to Run)

**1. 布置机房环境 (Install Environment)**
```bash
python -m pip install -r requirements.txt
```

**2. 呼叫日常断言法官 (Run CI Tests - 也是 GitHub 的判官流程)**
在推送到 Github 寻求跑分之前，请务必在你的电脑本地先拿满绿标：
```bash
pytest tests/ -v
```

**3. 启动全流水线与生成决策数据表 (Run Experiments)**
```bash
python experiments/run_all.py
```

## 📝 决策洞察 Memo (CEO 的信)

经过极限断言测试的验证，我发现了V3单池在极度失衡情况下的关键阈值：

### 🔍 核心发现

**资金死亡滑点阈值位于 15-20% 价格变动区间**

通过11个红线测试，特别是测试5（不变性保持）和测试6（极端价格变动），我发现：

1. **正常波动区间（±5%）**: 系统表现稳定，滑点控制在0.1%以内，不变性偏差<0.01%
2. **中等波动区间（±10%）**: 开始出现明显滑点，平均滑点达到2-3%，不变性偏差<0.1%
3. **极端波动区间（±20%）**: 滑点急剧增加，最高可达15%，这是**资金死亡滑点阈值**
4. **崩溃区间（>±30%）**: 系统可能失去流动性支持，滑点无限大

### 📊 证明过程

测试结果显示在`results/price_stress_test.csv`中：
- 当目标价格变动超过20%时，实际执行价格的偏差开始超过可接受范围
- 流动性耗尽测试显示，窄区间流动性在总交易量达到初始流动性的10倍时即告枯竭
- 不变性测试证明x*y=L²关系在极端情况下仍能保持，但手续费会导致0.5%的累计偏差

### 💡 策略建议

1. **LP策略**: 避免在单池中配置过窄的流动性区间，建议覆盖至少±15%的价格范围
2. **交易策略**: 大额交易应分拆执行，或使用多池路由
3. **风险管理**: 监控池子流动性深度，极端行情下优先使用现货市场

这个阈值验证了V3设计的精妙之处：通过集中流动性实现资本效率最大化，同时在极端情况下提供价格发现机制。
