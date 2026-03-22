"""
Complete Backtest Performance Metrics Calculator
Paste this into any notebook after running the backtest.

Requires:
  - trades_df : DataFrame with columns ['net_pnl', 'fees', 'hold_ticks', 'exit_reason', 'gross_pnl']
  - equity_df : DataFrame with columns ['tick', 'capital']
  - INITIAL_CAPITAL : float
"""

import numpy as np
import pandas as pd


def compute_all_metrics(trades_df, equity_df, initial_capital, ticks_per_day=390):
    """
    Computes every relevant backtest ratio from trades and equity data.

    Returns a dict of all metrics + prints a formatted report.
    """

    if trades_df.empty:
        print('⚠️ No trades to analyze.')
        return {}

    pnl = trades_df['net_pnl']
    n = len(pnl)
    winners = pnl[pnl > 0]
    losers = pnl[pnl <= 0]
    total_pnl = pnl.sum()
    total_fees = trades_df['fees'].sum()
    final_capital = equity_df['capital'].iloc[-1]
    cap = equity_df['capital'].values

    # ─────────────────────────────────────────────────
    # 1. RETURN METRICS
    # ─────────────────────────────────────────────────

    total_return_pct = (final_capital - initial_capital) / initial_capital * 100

    # Approximate annualized return (assuming 252 trading days)
    n_ticks = equity_df['tick'].iloc[-1] - equity_df['tick'].iloc[0]
    n_days = max(n_ticks / ticks_per_day, 1)
    annualized_return = ((final_capital / initial_capital) ** (252 / n_days) - 1) * 100

    # ─────────────────────────────────────────────────
    # 2. RISK METRICS
    # ─────────────────────────────────────────────────

    # Max Drawdown
    peak = np.maximum.accumulate(cap)
    drawdown = (peak - cap) / peak
    max_drawdown_pct = drawdown.max() * 100

    # Max Drawdown Duration (ticks)
    in_dd = drawdown > 0
    dd_durations = []
    dd_start = None
    for i in range(len(in_dd)):
        if in_dd[i] and dd_start is None:
            dd_start = i
        elif not in_dd[i] and dd_start is not None:
            dd_durations.append(i - dd_start)
            dd_start = None
    if dd_start is not None:
        dd_durations.append(len(in_dd) - dd_start)
    max_dd_duration = max(dd_durations) if dd_durations else 0

    # ─────────────────────────────────────────────────
    # 3. RISK-ADJUSTED RETURN RATIOS
    # ─────────────────────────────────────────────────

    # Per-trade returns (as fraction of capital)
    trade_returns = pnl / initial_capital

    # Sharpe Ratio (annualized)
    # Annualize by sqrt(trades_per_year)
    trades_per_day = n / max(n_days, 1)
    trades_per_year = trades_per_day * 252
    if trade_returns.std() > 0:
        sharpe = (trade_returns.mean() / trade_returns.std()) * np.sqrt(trades_per_year)
    else:
        sharpe = 0.0

    # Sortino Ratio (annualized) — only penalizes downside vol
    downside_returns = trade_returns[trade_returns < 0]
    if len(downside_returns) > 0 and downside_returns.std() > 0:
        sortino = (trade_returns.mean() / downside_returns.std()) * np.sqrt(trades_per_year)
    else:
        sortino = float('inf') if trade_returns.mean() > 0 else 0.0

    # Calmar Ratio — annualized return / max drawdown
    calmar = annualized_return / max_drawdown_pct if max_drawdown_pct > 0 else 0.0

    # ─────────────────────────────────────────────────
    # 4. WIN/LOSS METRICS
    # ─────────────────────────────────────────────────

    win_rate = len(winners) / n * 100
    loss_rate = 100 - win_rate

    avg_win = winners.mean() if len(winners) > 0 else 0
    avg_loss = losers.mean() if len(losers) > 0 else 0
    largest_win = winners.max() if len(winners) > 0 else 0
    largest_loss = losers.min() if len(losers) > 0 else 0

    # Profit Factor — gross wins / gross losses
    gross_profit = winners.sum() if len(winners) > 0 else 0
    gross_loss = abs(losers.sum()) if len(losers) > 0 else 1
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

    # Payoff Ratio — avg win / avg loss
    payoff_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')

    # Expectancy — expected $ per trade
    expectancy = (win_rate / 100 * avg_win) + (loss_rate / 100 * avg_loss)

    # Kelly Criterion — optimal fraction to bet
    # Kelly = W - (1-W)/R where W=win rate, R=payoff ratio
    if payoff_ratio > 0 and payoff_ratio != float('inf'):
        kelly = (win_rate / 100) - ((1 - win_rate / 100) / payoff_ratio)
    else:
        kelly = 0.0

    # ─────────────────────────────────────────────────
    # 5. CONSISTENCY METRICS
    # ─────────────────────────────────────────────────

    # Consecutive wins/losses
    streaks_win = []
    streaks_loss = []
    current_w = 0
    current_l = 0
    for p in pnl:
        if p > 0:
            current_w += 1
            if current_l > 0:
                streaks_loss.append(current_l)
            current_l = 0
        else:
            current_l += 1
            if current_w > 0:
                streaks_win.append(current_w)
            current_w = 0
    if current_w > 0:
        streaks_win.append(current_w)
    if current_l > 0:
        streaks_loss.append(current_l)

    max_consec_wins = max(streaks_win) if streaks_win else 0
    max_consec_losses = max(streaks_loss) if streaks_loss else 0

    # Skewness and Kurtosis of P&L
    skewness = pnl.skew()
    kurtosis = pnl.kurtosis()

    # ─────────────────────────────────────────────────
    # 6. EFFICIENCY METRICS
    # ─────────────────────────────────────────────────

    avg_hold = trades_df['hold_ticks'].mean()
    total_hold = trades_df['hold_ticks'].sum()
    time_in_market_pct = total_hold / max(n_ticks, 1) * 100

    # Return per tick in market
    return_per_tick = total_pnl / max(total_hold, 1)

    # Fee drag — fees as % of gross profit
    gross_total = trades_df['gross_pnl'].sum() if 'gross_pnl' in trades_df.columns else total_pnl + total_fees
    fee_drag_pct = total_fees / abs(gross_total) * 100 if gross_total != 0 else 0

    # ─────────────────────────────────────────────────
    # BUILD RESULTS DICT
    # ─────────────────────────────────────────────────

    metrics = {
        # Returns
        'total_pnl': total_pnl,
        'total_return_pct': total_return_pct,
        'annualized_return_pct': annualized_return,
        'final_capital': final_capital,

        # Risk
        'max_drawdown_pct': max_drawdown_pct,
        'max_dd_duration_ticks': max_dd_duration,

        # Risk-adjusted
        'sharpe_ratio': sharpe,
        'sortino_ratio': sortino,
        'calmar_ratio': calmar,

        # Win/loss
        'total_trades': n,
        'winners': len(winners),
        'losers': len(losers),
        'win_rate_pct': win_rate,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'largest_win': largest_win,
        'largest_loss': largest_loss,
        'profit_factor': profit_factor,
        'payoff_ratio': payoff_ratio,
        'expectancy_per_trade': expectancy,
        'kelly_criterion': kelly,

        # Consistency
        'max_consec_wins': max_consec_wins,
        'max_consec_losses': max_consec_losses,
        'pnl_skewness': skewness,
        'pnl_kurtosis': kurtosis,

        # Efficiency
        'avg_hold_ticks': avg_hold,
        'time_in_market_pct': time_in_market_pct,
        'return_per_tick': return_per_tick,
        'total_fees': total_fees,
        'fee_drag_pct': fee_drag_pct,
    }

    # ─────────────────────────────────────────────────
    # PRINT REPORT
    # ─────────────────────────────────────────────────

    print('═' * 62)
    print('         📈 COMPLETE BACKTEST PERFORMANCE REPORT')
    print('═' * 62)

    print('\n  ── RETURNS ──')
    print(f'    Initial Capital        : ${initial_capital:>14,.2f}')
    print(f'    Final Capital          : ${final_capital:>14,.2f}')
    print(f'    Total Net P&L          : ${total_pnl:>14,.2f}')
    print(f'    Total Return           : {total_return_pct:>13.3f}%')
    print(f'    Annualized Return      : {annualized_return:>13.2f}%')

    print('\n  ── RISK ──')
    print(f'    Max Drawdown           : {max_drawdown_pct:>13.4f}%')
    print(f'    Max DD Duration        : {max_dd_duration:>13} ticks')

    print('\n  ── RISK-ADJUSTED RATIOS ──')
    print(f'    Sharpe Ratio (ann.)    : {sharpe:>13.2f}')
    print(f'    Sortino Ratio (ann.)   : {sortino:>13.2f}')
    print(f'    Calmar Ratio           : {calmar:>13.2f}')

    print('\n  ── WIN/LOSS ──')
    print(f'    Total Trades           : {n:>13}')
    print(f'    Win Rate               : {win_rate:>12.1f}%')
    print(f'    Avg Win                : ${avg_win:>14,.2f}')
    print(f'    Avg Loss               : ${avg_loss:>14,.2f}')
    print(f'    Largest Win            : ${largest_win:>14,.2f}')
    print(f'    Largest Loss           : ${largest_loss:>14,.2f}')
    print(f'    Profit Factor          : {profit_factor:>13.2f}')
    print(f'    Payoff Ratio           : {payoff_ratio:>13.2f}')
    print(f'    Expectancy / Trade     : ${expectancy:>14,.2f}')
    print(f'    Kelly Criterion        : {kelly:>13.2f}')

    print('\n  ── CONSISTENCY ──')
    print(f'    Max Consec. Wins       : {max_consec_wins:>13}')
    print(f'    Max Consec. Losses     : {max_consec_losses:>13}')
    print(f'    P&L Skewness           : {skewness:>13.2f}')
    print(f'    P&L Kurtosis           : {kurtosis:>13.2f}')

    print('\n  ── EFFICIENCY ──')
    print(f'    Avg Hold Time          : {avg_hold:>12.1f} ticks')
    print(f'    Time in Market         : {time_in_market_pct:>12.1f}%')
    print(f'    Return / Tick in Mkt   : ${return_per_tick:>14,.2f}')
    print(f'    Total Fees Paid        : ${total_fees:>14,.2f}')
    print(f'    Fee Drag (% of gross)  : {fee_drag_pct:>12.1f}%')

    print('\n' + '═' * 62)

    return metrics


# ─────────────────────────────────────────────────
# USAGE: paste this after your backtest runs
# ─────────────────────────────────────────────────
# metrics = compute_all_metrics(trades_df, equity_df, INITIAL_CAPITAL)
