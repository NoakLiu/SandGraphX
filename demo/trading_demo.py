#!/usr/bin/env python3
"""
SandGraph 交易环境演示 - 基于RL的LLM决策架构

新的架构设计：
1. Sandbox作为环境节点
2. LLM作为决策器（不是节点）
3. RL算法更新LLM权重
4. 状态转移由LLM决策驱动
"""

import sys
import os
import time
import json
import argparse
import random
from typing import Dict, Any, List, Union
from datetime import datetime, timedelta

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sandgraph.core.llm_interface import create_shared_llm_manager
from sandgraph.core.sg_workflow import (
    SG_Workflow, WorkflowMode, EnhancedWorkflowNode,
    NodeType, NodeCondition, NodeLimits, GameState
)
from sandgraph.core.rl_algorithms import RLTrainer, RLConfig, RLAlgorithm
from sandgraph.sandbox_implementations import TradingSandbox


def print_section(title: str):
    """打印章节标题"""
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}")


class LLMDecisionMaker:
    """LLM决策器 - 不是节点，而是决策引擎"""
    
    def __init__(self, llm_manager):
        self.llm_manager = llm_manager
        self.decision_count = 0
        
        # 历史数据管理
        self.decision_history = []  # 决策历史
        self.market_history = []    # 市场数据历史
        self.portfolio_history = [] # 投资组合历史
        self.performance_history = [] # 表现历史
        
        # 注册决策节点
        self.llm_manager.register_node("trading_decision", {
            "role": "交易决策专家",
            "reasoning_type": "strategic",
            "temperature": 0.7,
            "max_length": 512
        })
    
    def make_decision(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """基于当前状态做出交易决策"""
        self.decision_count += 1
        
        # 构造决策提示（包含历史数据）
        prompt = self._construct_decision_prompt(state)
        print(f"\n{'='*80}")
        print(f"Decision {self.decision_count} - Complete Prompt Content:")
        print(f"{'='*80}")
        print(prompt)
        print(f"{'='*80}")
        
        # 使用LLM生成决策
        try:
            response = self.llm_manager.generate_for_node(
                "trading_decision", 
                prompt,
                temperature=0.7,
                max_new_tokens=128,  # 使用max_new_tokens而不是max_length
                do_sample=True,
                pad_token_id=self.llm_manager.tokenizer.eos_token_id if hasattr(self.llm_manager, 'tokenizer') else None
            )
            print(f"\nLLM Response Status: {response.status if hasattr(response, 'status') else 'unknown'}")
            print(f"LLM Complete Response: {response.text}")
        except Exception as e:
            print(f"LLM Call Error: {e}")
            # 如果LLM调用失败，使用简单的规则决策
            return self._fallback_decision(state)
        
        # 解析决策
        decision = self._parse_decision(response.text, state)
        
        # 更新历史数据
        self._update_history(state, decision, response.text)
        
        return {
            "decision": decision,
            "llm_response": response.text,
            "prompt": prompt,
            "decision_count": self.decision_count
        }
    
    def _update_history(self, state: Dict[str, Any], decision: Dict[str, Any], llm_response: str):
        """更新历史数据"""
        # 记录决策历史
        decision_record = {
            "step": self.decision_count,
            "timestamp": datetime.now().isoformat(),
            "decision": decision,
            "llm_response": llm_response,
            "market_data": state.get("market_data", {}),
            "portfolio": state.get("portfolio", {}),
            "technical_indicators": state.get("technical_indicators", {}),
            "detailed_history": state.get("detailed_history", {})
        }
        self.decision_history.append(decision_record)
        
        # 保持历史记录在合理范围内
        if len(self.decision_history) > 50:
            self.decision_history = self.decision_history[-50:]
        
        # 记录市场数据历史
        market_record = {
            "step": self.decision_count,
            "market_data": state.get("market_data", {}),
            "detailed_history": state.get("detailed_history", {})
        }
        self.market_history.append(market_record)
        
        # 记录投资组合历史
        portfolio_record = {
            "step": self.decision_count,
            "portfolio": state.get("portfolio", {}),
            "total_value": self._calculate_total_portfolio_value(state)
        }
        self.portfolio_history.append(portfolio_record)
        
        # 保持历史记录在合理范围内
        if len(self.market_history) > 30:
            self.market_history = self.market_history[-30:]
        if len(self.portfolio_history) > 30:
            self.portfolio_history = self.portfolio_history[-30:]
    
    def _calculate_total_portfolio_value(self, state: Dict[str, Any]) -> float:
        """计算投资组合总价值"""
        portfolio = state.get("portfolio", {})
        market_data = state.get("market_data", {})
        
        cash = portfolio.get("cash", 0)
        positions = portfolio.get("positions", {})
        
        position_value = 0
        for symbol, amount in positions.items():
            if symbol in market_data and "close" in market_data[symbol]:
                position_value += amount * market_data[symbol]["close"]
        
        return cash + position_value
    
    def _construct_decision_prompt(self, state: Dict[str, Any]) -> str:
        """构造决策提示（包含历史数据）"""
        market_data = state.get("market_data", {})
        portfolio = state.get("portfolio", {})
        price_history = state.get("price_history", {})
        technical_indicators = state.get("technical_indicators", {})
        trade_history = state.get("trade_history", [])
        detailed_history = state.get("detailed_history", {})
        
        # 构建市场数据摘要
        market_summary = []
        for symbol, data in market_data.items():
            market_summary.append(
                f"{symbol}: 价格={data.get('close', 0):.2f}, "
                f"开盘={data.get('open', 0):.2f}, "
                f"最高={data.get('high', 0):.2f}, "
                f"最低={data.get('low', 0):.2f}, "
                f"成交量={data.get('volume', 0)}"
            )
        
        # 构建技术指标摘要
        technical_summary = []
        for symbol, indicators in technical_indicators.items():
            technical_summary.append(
                f"{symbol}技术指标:\n"
                f"  MA5={indicators.get('ma5', 0):.2f}, MA10={indicators.get('ma10', 0):.2f}, MA20={indicators.get('ma20', 0):.2f}\n"
                f"  RSI={indicators.get('rsi', 0):.1f}, MACD={indicators.get('macd', 0):.2f}\n"
                f"  趋势={indicators.get('price_trend', 'unknown')}, 动量={indicators.get('momentum', 'unknown')}\n"
                f"  布林带上轨={indicators.get('bollinger_upper', 0):.2f}, 下轨={indicators.get('bollinger_lower', 0):.2f}"
            )
        
        # 构建过去10天详细历史数据
        detailed_history_summary = []
        for symbol, history_data in detailed_history.items():
            if "error" in history_data:
                continue
                
            summary = history_data["summary"]
            analysis = history_data["analysis"]
            
            detailed_history_summary.append(f"\n{symbol} 过去10天详细分析:")
            detailed_history_summary.append(f"累计涨跌幅: {summary['total_change_str']}")
            detailed_history_summary.append(f"趋势方向: {summary['trend_direction']} ({summary['trend_strength_str']})")
            detailed_history_summary.append(f"价格波动: {summary['volatility_str']}")
            detailed_history_summary.append(f"成交量趋势: {summary['volume_trend']} (平均: {summary['avg_volume']:,})")
            detailed_history_summary.append(f"价格区间: {summary['min_low']:.2f} - {summary['max_high']:.2f}")
            detailed_history_summary.append(f"价格动量: {analysis['price_momentum']}")
            detailed_history_summary.append(f"量能支撑: {analysis['volume_support']}")
            detailed_history_summary.append(f"波动水平: {analysis['volatility_level']}")
            detailed_history_summary.append(f"趋势质量: {analysis['trend_quality']}")
            
            # 添加每日详细数据表格
            detailed_history_summary.append("\n每日详细数据:")
            detailed_history_summary.append("日期\t开盘\t最高\t最低\t收盘\t成交量\t涨跌幅")
            detailed_history_summary.append("-" * 60)
            
            for day_data in history_data["daily_data"]:
                detailed_history_summary.append(
                    f"{day_data['date']}\t{day_data['open']:.2f}\t{day_data['high']:.2f}\t"
                    f"{day_data['low']:.2f}\t{day_data['close']:.2f}\t{day_data['volume']:,}\t{day_data['change_str']}"
                )
        
        # 构建决策历史摘要
        decision_history_summary = []
        if self.decision_history:
            decision_history_summary.append("\n=== Recent Decision History ===")
            recent_decisions = self.decision_history[-10:]  # 最近10次决策
            for record in recent_decisions:
                decision = record["decision"]
                step = record["step"]
                decision_history_summary.append(
                    f"Step {step}: {decision.get('action', '')} {decision.get('symbol', '')} "
                    f"{decision.get('amount', '')} shares - Reason: {decision.get('reasoning', '')[:50]}..."
                )
        
        # 构建投资组合历史摘要
        portfolio_history_summary = []
        if self.portfolio_history:
            portfolio_history_summary.append("\n=== Portfolio Change History ===")
            recent_portfolios = self.portfolio_history[-10:]  # 最近10次投资组合状态
            for i, record in enumerate(recent_portfolios):
                step = record["step"]
                total_value = record["total_value"]
                portfolio_history_summary.append(f"Step {step}: Total Value {total_value:.2f}")
                
                # 计算投资组合变化
                if i > 0:
                    prev_value = recent_portfolios[i-1]["total_value"]
                    if prev_value > 0:
                        change_pct = (total_value - prev_value) / prev_value * 100
                        portfolio_history_summary[-1] += f" (Change: {change_pct:+.2f}%)"
        
        # 构建价格历史摘要（保持原有的简化版本）
        history_summary = []
        for symbol, history in price_history.items():
            if len(history) >= 5:
                recent_prices = [p["close"] for p in history[-5:]]
                price_changes = []
                for i in range(1, len(recent_prices)):
                    change = (recent_prices[i] - recent_prices[i-1]) / recent_prices[i-1] * 100
                    price_changes.append(f"{change:+.2f}%")
                
                history_summary.append(
                    f"{symbol}最近5天价格变化: {' → '.join(price_changes)}"
                )
        
        # 构建交易历史摘要
        trade_summary = []
        if trade_history:
            recent_trades = trade_history[-10:]  # 最近10笔交易
            for trade in recent_trades:
                trade_summary.append(
                    f"步骤{trade.get('step', 0)}: {trade.get('action', '')} {trade.get('symbol', '')} "
                    f"{trade.get('amount', 0)}股 @ {trade.get('price', 0):.2f} "
                    f"(评分: {trade.get('score', 0):.3f})"
                )
        
        # 构建投资组合摘要
        cash = portfolio.get("cash", 0)
        positions = portfolio.get("positions", {})
        position_summary = []
        for symbol, amount in positions.items():
            position_summary.append(f"{symbol}: {amount} 股")
        
        return f"""You are a professional trading decision expert. This is a SIMULATION GAME for testing purposes - NOT real stock trading. Please do not be cautious or conservative. You MUST provide SPECIFIC BUY or SELL actions with exact quantities.

This is a numerical simulation game where the goal is to make optimal trading decisions based on the data. Do not worry about real-world risks or consequences.

Please make trading decisions based on the following detailed market information:

=== Current Market Data ===
{chr(10).join(market_summary)}

=== Technical Indicators Analysis ===
{chr(10).join(technical_summary)}

=== Past 10 Days Detailed Market Analysis ===
{chr(10).join(detailed_history_summary)}

=== Price History Trends ===
{chr(10).join(history_summary)}

=== Recent Trading Records ===
{chr(10).join(trade_summary) if trade_summary else 'No trading records'}

{chr(10).join(decision_history_summary) if decision_history_summary else ''}

{chr(10).join(portfolio_history_summary) if portfolio_history_summary else ''}

=== Current Portfolio ===
Cash: {cash:.2f}
Positions: {chr(10).join(position_summary) if position_summary else 'None'}

=== Decision Guidelines ===
Please analyze based on the following factors:
1. Price trends: 10-day cumulative change, trend strength, price momentum
2. Technical indicators: RSI overbought/oversold, MACD signals, MA5 vs MA20 relationship
3. Bollinger Bands: whether price is near support/resistance levels
4. Volume analysis: volume trends, volume support
5. Volatility analysis: price range, volatility level
6. Historical performance: recent trading success rate, decision history performance
7. Portfolio changes: total value change trends
8. Risk control: current positions and cash status

CRITICAL: This is a simulation game! You MUST provide a SPECIFIC action with exact quantities. NO cautious strategies, NO holding, NO vague responses!

Please choose one of the following and provide EXACT quantities:
1. Buy stocks: write "BUY [symbol] [exact_amount] shares"
2. Sell stocks: write "SELL [symbol] [exact_amount] shares"

Examples: BUY AAPL 150 shares, SELL GOOGL 75 shares

Please provide your decision with exact quantities and briefly explain your reasoning:"""

    def _parse_decision(self, response: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """解析LLM的决策响应"""
        print(f"Original LLM Response: {response[:200]}...")  # 调试信息
        
        # 清理响应文本
        response = response.strip()
        
        # 强制要求买入或卖出，不允许HOLD
        symbols = state.get("symbols", ["AAPL", "GOOGL", "MSFT", "AMZN"])
        market_data = state.get("market_data", {})
        
        # 方式1: 查找中文买入/卖出关键词
        if "买入" in response:
            # 尝试提取股票代码和数量
            for symbol in symbols:
                if symbol in response:
                    # 尝试提取数量
                    import re
                    amount_match = re.search(r'(\d+(?:\.\d+)?)', response)
                    amount = float(amount_match.group(1)) if amount_match else 100
                    return {
                        "action": "BUY",
                        "symbol": symbol,
                        "amount": amount,
                        "reasoning": response
                    }
        
        if "卖出" in response:
            # 尝试提取股票代码和数量
            for symbol in symbols:
                if symbol in response:
                    # 尝试提取数量
                    import re
                    amount_match = re.search(r'(\d+(?:\.\d+)?)', response)
                    amount = float(amount_match.group(1)) if amount_match else 100
                    return {
                        "action": "SELL",
                        "symbol": symbol,
                        "amount": amount,
                        "reasoning": response
                    }
        
        # 方式2: 查找英文BUY/SELL关键词
        response_upper = response.upper()
        
        # 查找BUY决策
        if "BUY" in response_upper:
            for symbol in symbols:
                if symbol in response_upper:
                    import re
                    amount_match = re.search(r'(\d+(?:\.\d+)?)', response)
                    amount = float(amount_match.group(1)) if amount_match else 100
                    return {
                        "action": "BUY",
                        "symbol": symbol,
                        "amount": amount,
                        "reasoning": response
                    }
        
        # 查找SELL决策
        if "SELL" in response_upper:
            for symbol in symbols:
                if symbol in response_upper:
                    import re
                    amount_match = re.search(r'(\d+(?:\.\d+)?)', response)
                    amount = float(amount_match.group(1)) if amount_match else 100
                    return {
                        "action": "SELL",
                        "symbol": symbol,
                        "amount": amount,
                        "reasoning": response
                    }
        
        # 方式3: 基于市场分析做智能决策（强制买入或卖出）
        if market_data:
            # 分析每个股票的技术指标
            best_buy_symbol = None
            best_buy_score = -1
            best_sell_symbol = None
            best_sell_score = -1
            
            for symbol in symbols:
                if symbol in market_data:
                    # 获取技术指标
                    technical_indicators = state.get("technical_indicators", {}).get(symbol, {})
                    
                    # 计算买入评分
                    rsi = technical_indicators.get("rsi", 50)
                    ma5 = technical_indicators.get("ma5", 0)
                    ma20 = technical_indicators.get("ma20", 0)
                    price = market_data[symbol]["close"]
                    
                    # 买入条件：RSI < 70 (非超买)，MA5 > MA20 (上涨趋势)
                    buy_score = 0
                    if rsi < 70:  # 非超买
                        buy_score += 0.3
                    if ma5 > ma20:  # 上涨趋势
                        buy_score += 0.4
                    if ma5 > 0 and ma20 > 0:
                        trend_strength = (ma5 - ma20) / ma20
                        buy_score += min(0.3, trend_strength * 10)
                    
                    # 卖出条件：RSI > 30 (非超卖)，MA5 < MA20 (下跌趋势)
                    sell_score = 0
                    if rsi > 30:  # 非超卖
                        sell_score += 0.3
                    if ma5 < ma20:  # 下跌趋势
                        sell_score += 0.4
                    if ma5 > 0 and ma20 > 0:
                        trend_strength = (ma20 - ma5) / ma20
                        sell_score += min(0.3, trend_strength * 10)
                    
                    # 更新最佳选择
                    if buy_score > best_buy_score:
                        best_buy_score = buy_score
                        best_buy_symbol = symbol
                    
                    if sell_score > best_sell_score:
                        best_sell_score = sell_score
                        best_sell_symbol = symbol
            
            # 选择评分更高的操作
            if best_buy_score > best_sell_score and best_buy_score > 0.3:
                return {
                    "action": "BUY",
                    "symbol": best_buy_symbol,
                    "amount": 100,
                    "reasoning": f"基于技术分析，{best_buy_symbol}呈现买入信号（RSI: {technical_indicators.get('rsi', 0):.1f}, 趋势: 上涨）"
                }
            elif best_sell_score > 0.3:
                return {
                    "action": "SELL",
                    "symbol": best_sell_symbol,
                    "amount": 100,
                    "reasoning": f"基于技术分析，{best_sell_symbol}呈现卖出信号（RSI: {technical_indicators.get('rsi', 0):.1f}, 趋势: 下跌）"
                }
        
        # 方式4: 如果所有解析都失败，强制买入表现最好的股票
        if market_data:
            # 选择涨幅最大的股票买入
            best_symbol = max(market_data.keys(), 
                            key=lambda s: market_data[s].get("close", 0) - market_data[s].get("open", 0))
            return {
                "action": "BUY",
                "symbol": best_symbol,
                "amount": 100,
                "reasoning": f"强制决策：选择买入{best_symbol}（当日涨幅最大）"
            }
        
        # 最后的备用方案
        if symbols:
            return {
                "action": "BUY",
                "symbol": symbols[0],
                "amount": 100,
                "reasoning": f"备用决策：买入{symbols[0]}（默认选择）"
            }
        
        # 如果连股票列表都没有，返回错误
        return {
            "action": "BUY",
            "symbol": "AAPL",
            "amount": 100,
            "reasoning": "错误：无法解析决策，使用默认买入AAPL"
        }

    def _fallback_decision(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """LLM调用失败时的备用决策"""
        market_data = state.get("market_data", {})
        if not market_data:
            # 如果没有市场数据，强制买入第一个股票
            symbols = state.get("symbols", ["AAPL", "GOOGL", "MSFT", "AMZN"])
            return {
                "action": "BUY",
                "symbol": symbols[0],
                "amount": 100,
                "reasoning": "备用决策：无市场数据，买入默认股票"
            }
        
        # 分析市场数据，选择最佳买入或卖出
        symbols = list(market_data.keys())
        if symbols:
            # 计算每个股票的评分
            best_buy_symbol = None
            best_buy_score = -1
            best_sell_symbol = None
            best_sell_score = -1
            
            for symbol in symbols:
                symbol_data = market_data[symbol]
                technical_indicators = state.get("technical_indicators", {}).get(symbol, {})
                
                # 计算买入评分
                rsi = technical_indicators.get("rsi", 50)
                ma5 = technical_indicators.get("ma5", 0)
                ma20 = technical_indicators.get("ma20", 0)
                
                buy_score = 0
                if rsi < 70:  # 非超买
                    buy_score += 0.3
                if ma5 > ma20:  # 上涨趋势
                    buy_score += 0.4
                if ma5 > 0 and ma20 > 0:
                    trend_strength = (ma5 - ma20) / ma20
                    buy_score += min(0.3, trend_strength * 10)
                
                # 计算卖出评分
                sell_score = 0
                if rsi > 30:  # 非超卖
                    sell_score += 0.3
                if ma5 < ma20:  # 下跌趋势
                    sell_score += 0.4
                if ma5 > 0 and ma20 > 0:
                    trend_strength = (ma20 - ma5) / ma20
                    sell_score += min(0.3, trend_strength * 10)
                
                # 更新最佳选择
                if buy_score > best_buy_score:
                    best_buy_score = buy_score
                    best_buy_symbol = symbol
                
                if sell_score > best_sell_score:
                    best_sell_score = sell_score
                    best_sell_symbol = symbol
            
            # 选择评分更高的操作
            if best_buy_score > best_sell_score and best_buy_score > 0.3:
                return {
                    "action": "BUY",
                    "symbol": best_buy_symbol,
                    "amount": 100,
                    "reasoning": f"备用决策：基于技术分析买入{best_buy_symbol}"
                }
            elif best_sell_score > 0.3:
                return {
                    "action": "SELL",
                    "symbol": best_sell_symbol,
                    "amount": 100,
                    "reasoning": f"备用决策：基于技术分析卖出{best_sell_symbol}"
                }
            else:
                # 如果技术分析不明确，选择买入涨幅最大的股票
                best_symbol = max(symbols, 
                                key=lambda s: market_data[s].get("close", 0) - market_data[s].get("open", 0))
                return {
                    "action": "BUY",
                    "symbol": best_symbol,
                    "amount": 100,
                    "reasoning": f"备用决策：买入{best_symbol}（涨幅最大）"
                }
        
        # 最后的备用方案
        return {
            "action": "BUY",
            "symbol": "AAPL",
            "amount": 100,
            "reasoning": "备用决策：买入AAPL（默认选择）"
        }


def create_rl_trading_workflow(llm_manager, strategy_type: str = "simulated") -> tuple[SG_Workflow, RLTrainer, LLMDecisionMaker]:
    """创建基于RL的LLM决策交易工作流 - 使用纯模拟数据"""
    
    # 创建RL配置
    rl_config = RLConfig(
        algorithm=RLAlgorithm.PPO,
        learning_rate=3e-4,
        gamma=0.99,
        gae_lambda=0.95,
        clip_ratio=0.2,
        value_loss_coef=0.5,
        entropy_coef=0.01,
        max_grad_norm=0.5,
        batch_size=32,
        mini_batch_size=8,
        ppo_epochs=4,
        target_kl=0.01
    )
    
    # 创建RL训练器
    rl_trainer = RLTrainer(rl_config, llm_manager)
    
    # 创建LLM决策器
    decision_maker = LLMDecisionMaker(llm_manager)
    
    # 创建工作流
    workflow = SG_Workflow("rl_trading_workflow", WorkflowMode.TRADITIONAL, llm_manager)
    
    # 创建交易沙盒
    sandbox = TradingSandbox(
        initial_balance=100000.0,
        symbols=["AAPL", "GOOGL", "MSFT", "AMZN"]
    )
    
    # 创建交易环境节点
    def trading_env_func(inputs: Dict[str, Any]) -> Dict[str, Any]:
        """交易环境节点函数"""
        # 获取当前状态
        case = sandbox.case_generator()
        current_state = case["state"]
        
        # 使用LLM做出决策
        decision_result = decision_maker.make_decision(current_state)
        decision = decision_result["decision"]
        
        # 执行交易决策
        try:
            # 验证和执行交易
            score = sandbox.verify_score(
                f"{decision['action']} {decision.get('symbol', '')} {decision.get('amount', 0)}",
                case
            )
            
            # 计算奖励
            reward = score * 10  # 将分数转换为奖励
            
            # 构建状态特征
            state_features = {
                "market_volatility": _calculate_volatility(current_state),
                "portfolio_value": _calculate_portfolio_value(current_state),
                "cash_ratio": current_state["portfolio"]["cash"] / 100000.0,
                "position_count": len(current_state["portfolio"]["positions"]),
                "decision_type": 1 if decision["action"] == "BUY" else (2 if decision["action"] == "SELL" else 0)
            }
            
            # 添加到RL训练器
            rl_trainer.add_experience(
                state=state_features,
                action=json.dumps(decision),
                reward=reward,
                done=False
            )
            
            # 更新策略
            update_result = rl_trainer.update_policy()
            
            return {
                "state": current_state,
                "decision": decision,
                "llm_response": decision_result["llm_response"],
                "score": score,
                "reward": reward,
                "rl_update": update_result,
                "sandbox_id": sandbox.sandbox_id
            }
            
        except Exception as e:
            print(f"交易执行错误: {e}")
            return {
                "state": current_state,
                "decision": {"action": "HOLD", "reasoning": f"执行错误: {e}"},
                "score": 0.0,
                "reward": 0.0,
                "error": str(e)
            }
    
    # 添加交易环境节点
    trading_env_node = EnhancedWorkflowNode(
        "trading_environment",
        NodeType.SANDBOX,
        sandbox=sandbox,
        condition=NodeCondition(),
        limits=NodeLimits(max_visits=10, resource_cost={"energy": 10, "tokens": 5})
    )
    workflow.add_node(trading_env_node)
    
    return workflow, rl_trainer, decision_maker


def _calculate_volatility(state: Dict[str, Any]) -> float:
    """计算市场波动性"""
    prices = []
    for symbol_data in state.get("market_data", {}).values():
        if "close" in symbol_data:
            prices.append(symbol_data["close"])
    
    if len(prices) < 2:
        return 0.5
    
    # 计算价格变化率的标准差
    returns = []
    for i in range(1, len(prices)):
        if prices[i-1] > 0:
            returns.append(abs(prices[i] - prices[i-1]) / prices[i-1])
    
    if not returns:
        return 0.5
    
    return min(1.0, sum(returns) / len(returns) * 10)


def _calculate_portfolio_value(state: Dict[str, Any]) -> float:
    """计算投资组合总价值"""
    cash = state["portfolio"]["cash"]
    positions = state["portfolio"]["positions"]
    market_data = state["market_data"]
    
    position_value = 0
    for symbol, amount in positions.items():
        if symbol in market_data and "close" in market_data[symbol]:
            position_value += amount * market_data[symbol]["close"]
    
    return cash + position_value


def run_rl_trading_demo(strategy_type: str = "simulated", steps: int = 5):
    """运行基于RL的LLM决策交易演示"""
    
    print_section(f"RL-based LLM Decision Trading Demo - {strategy_type.upper()}")
    
    # 1. 创建LLM管理器
    print("\n1. Creating LLM Manager")
    llm_manager = create_shared_llm_manager(
        model_name="Qwen/Qwen-7B-Chat",
        backend="huggingface",
        temperature=0.7,
        max_length=512,
        device="auto",
        torch_dtype="float16"
    )
    
    # 2. 创建工作流和RL训练器
    print("\n2. Creating RL Trading Workflow")
    workflow, rl_trainer, decision_maker = create_rl_trading_workflow(llm_manager, strategy_type)
    
    # 3. 执行多步交易
    print(f"\n3. Executing {steps} Trading Steps")
    
    results = []
    for step in range(steps):
        print(f"\n--- 第 {step + 1} 步 ---")
        
        try:
            # 直接执行交易环境节点
            node = workflow.nodes.get("trading_environment")
            if node and node.sandbox:
                # 获取当前状态
                case = node.sandbox.case_generator()
                current_state = case["state"]
                
                # 使用LLM做出决策
                decision_result = decision_maker.make_decision(current_state)
                decision = decision_result["decision"]
                
                # 执行交易决策
                try:
                    # 验证和执行交易
                    score = node.sandbox.verify_score(
                        f"{decision['action']} {decision.get('symbol', '')} {decision.get('amount', 0)}",
                        case
                    )
                    
                    # 计算奖励
                    reward = score * 10  # 将分数转换为奖励
                    
                    # 构建状态特征
                    state_features = {
                        "market_volatility": _calculate_volatility(current_state),
                        "portfolio_value": _calculate_portfolio_value(current_state),
                        "cash_ratio": current_state["portfolio"]["cash"] / 100000.0,
                        "position_count": len(current_state["portfolio"]["positions"]),
                        "decision_type": 1 if decision["action"] == "BUY" else (2 if decision["action"] == "SELL" else 0)
                    }
                    
                    # 添加到RL训练器
                    rl_trainer.add_experience(
                        state=state_features,
                        action=json.dumps(decision),
                        reward=reward,
                        done=False
                    )
                    
                    # 更新策略
                    update_result = rl_trainer.update_policy()
                    
                    result = {
                        "state": current_state,
                        "decision": decision,
                        "llm_response": decision_result["llm_response"],
                        "score": score,
                        "reward": reward,
                        "rl_update": update_result,
                        "sandbox_id": node.sandbox.sandbox_id
                    }
                    
                    print(f"LLM Decision: {decision['action']} {decision.get('symbol', '')} {decision.get('amount', '')}")
                    print(f"Decision Reason: {decision.get('reasoning', '')}")
                    print(f"Trading Score: {score:.3f}")
                    print(f"RL Reward: {reward:.3f}")
                    
                    # 显示RL更新状态
                    if "rl_update" in result:
                        rl_update = result["rl_update"]
                        print(f"RL Update Status: {rl_update.get('status', 'unknown')}")
                    
                    # 显示当前投资组合状态
                    portfolio = current_state.get("portfolio", {})
                    cash = portfolio.get("cash", 0)
                    positions = portfolio.get("positions", {})
                    print(f"Current Cash: {cash:.2f}")
                    print(f"Current Positions: {positions}")
                    
                    results.append(result)
                    
                except Exception as e:
                    print(f"❌ Trading Execution Error: {e}")
                    result = {
                        "state": current_state,
                        "decision": {"action": "HOLD", "reasoning": f"Execution Error: {e}"},
                        "score": 0.0,
                        "reward": 0.0,
                        "error": str(e)
                    }
                    results.append(result)
            else:
                print("❌ Trading Environment Node Not Found or Invalid")
                
        except Exception as e:
            print(f"❌ Step {step + 1} Execution Error: {e}")
    
    # 4. 输出最终结果
    print("\n4. Final Results")
    
    # 计算统计信息
    total_reward = sum(r.get("reward", 0) for r in results)
    avg_score = sum(r.get("score", 0) for r in results) / len(results) if results else 0
    decision_count = decision_maker.decision_count
    
    print(f"Total Decisions: {decision_count}")
    print(f"Total Reward: {total_reward:.3f}")
    print(f"Average Score: {avg_score:.3f}")
    
    # 显示RL训练统计
    rl_stats = rl_trainer.get_training_stats()
    print(f"RL Training Steps: {rl_stats['training_step']}")
    print(f"RL Algorithm: {rl_stats['algorithm']}")
    
    return results


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="基于RL的LLM决策交易演示")
    parser.add_argument(
        "--strategy",
        type=str,
        choices=["simulated"],
        default="simulated",
        help="选择交易策略类型"
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=5,
        help="交易步数"
    )
    args = parser.parse_args()
    
    run_rl_trading_demo(args.strategy, args.steps)


if __name__ == "__main__":
    main() 