#!/usr/bin/env python3
"""
TradeXBot Trading Bot CLI
Run trading sessions with detailed technical analysis logs
"""
import sys
import time
import argparse
from pathlib import Path

# Add the backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.trading_engine import trading_engine


def display_session_info(session):
    """Display current session information"""
    print("\n" + "="*60)
    print(f"  Trading Session: {session['pair']} | {session['timeframe']}")
    print(f"  Initial Balance: ${session['initial_balance']:.2f}")
    print("="*60 + "\n")


def display_trade_stats(session):
    """Display trade statistics"""
    total_trades = session['total_wins'] + session['total_losses']
    if total_trades == 0:
        return
    
    print("\n" + "-"*60)
    print(f"  Balance: ${session['current_balance']:.2f} | " + 
          f"Wins: {session['total_wins']} | " +
          f"Losses: {session['total_losses']} | " +
          f"Win Rate: {session['win_rate']:.0f}%")
    print("-"*60 + "\n")


def run_trading_session(pair="BTC/USDT", timeframe="1M", num_trades=5, delay_between_trades=3):
    """Run an interactive trading session"""
    
    try:
        # Start session
        session = trading_engine.start_session(pair=pair, timeframe=timeframe, initial_balance=200.0)
        display_session_info(session)
        
        input("Press Enter to start trading analysis...")
        
        # Execute trades
        for i in range(num_trades):
            print(f"\n{'='*60}")
            print(f"  TRADE #{i+1}")
            print(f"{'='*60}\n")
            
            try:
                # Execute trade
                result = trading_engine.execute_trade(pair=pair, amount=20.0, direction="BUY")
                
                # Display updated stats
                display_trade_stats(session)
                
                if i < num_trades - 1:
                    print(f"Next trade in {delay_between_trades} seconds...")
                    time.sleep(delay_between_trades)
                else:
                    input("\nPress Enter to end session...")
            
            except Exception as e:
                print(f"Error executing trade: {e}")
                break
        
        # End session and show summary
        print(f"\n{'='*60}")
        print("  ENDING SESSION...")
        print(f"{'='*60}\n")
        
        summary = trading_engine.end_session()
        
        print(f"\n{'='*60}")
        print("  SESSION SUMMARY")
        print(f"{'='*60}")
        print(f"Total Trades:    {summary['total_trades']}")
        print(f"Wins:            {summary['wins']}")
        print(f"Losses:          {summary['losses']}")
        print(f"Win Rate:        {summary['win_rate']:.0f}%")
        print(f"Duration:        {summary['duration']}")
        print(f"Starting Balance: ${summary['starting_balance']:.2f}")
        print(f"Ending Balance:   ${summary['ending_balance']:.2f}")
        print(f"Profit/Loss:     ${summary['profit_loss']:.2f}")
        print(f"{'='*60}\n")
        
        # Display all logs
        print("COMPLETE TRADE LOG:")
        print("-"*60)
        for log in summary['logs']:
            print(log)
        print("-"*60 + "\n")
        
    except KeyboardInterrupt:
        print("\n\nSession interrupted by user")
        if trading_engine.current_session:
            trading_engine.end_session()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


def run_multi_session_demo(num_sessions=3):
    """Run multiple trading sessions back-to-back"""
    
    for session_num in range(1, num_sessions + 1):
        print(f"\n\n{'#'*60}")
        print(f"# SESSION {session_num} of {num_sessions}")
        print(f"{'#'*60}\n")
        
        try:
            session = trading_engine.start_session(pair="BTC/USDT", timeframe="1M", initial_balance=200.0)
            display_session_info(session)
            
            # Quick auto-trading (3 trades per session)
            for trade_num in range(3):
                result = trading_engine.execute_trade(pair="BTC/USDT", amount=20.0, direction="BUY")
                display_trade_stats(session)
                
                if trade_num < 2:
                    time.sleep(2)
            
            summary = trading_engine.end_session()
            
            print(f"\nSession {session_num} Summary:")
            print(f"  Wins: {summary['wins']} | Losses: {summary['losses']} | Win Rate: {summary['win_rate']:.0f}%")
            print(f"  Balance: ${summary['ending_balance']:.2f} | P&L: ${summary['profit_loss']:.2f}")
            
            if session_num < num_sessions:
                print("\nStarting next session...")
                time.sleep(1)
        
        except Exception as e:
            print(f"Error in session {session_num}: {e}")
            break
    
    print(f"\n\n{'#'*60}")
    print("# ALL SESSIONS COMPLETED")
    print(f"{'#'*60}\n")


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="TradeXBot Trading Bot - Real-time trading simulation with technical analysis"
    )
    parser.add_argument("--mode", choices=["interactive", "demo", "multi"], default="interactive",
                       help="Trading mode: interactive (manual), demo (auto), or multi (multiple sessions)")
    parser.add_argument("--pair", default="BTC/USDT", help="Trading pair (default: BTC/USDT)")
    parser.add_argument("--timeframe", default="1M", help="Timeframe (default: 1M)")
    parser.add_argument("--trades", type=int, default=5, help="Number of trades (default: 5)")
    parser.add_argument("--delay", type=int, default=3, help="Delay between trades in seconds (default: 3)")
    parser.add_argument("--sessions", type=int, default=3, help="Number of sessions for multi mode (default: 3)")
    
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("  TradeXBot Trading Bot - AI Trading Engine")
    print("  With Advanced Technical Analysis")
    print("="*60 + "\n")
    
    if args.mode == "interactive":
        run_trading_session(
            pair=args.pair,
            timeframe=args.timeframe,
            num_trades=args.trades,
            delay_between_trades=args.delay
        )
    elif args.mode == "demo":
        print("Running automated demo mode...\n")
        run_trading_session(
            pair=args.pair,
            timeframe=args.timeframe,
            num_trades=args.trades,
            delay_between_trades=1
        )
    elif args.mode == "multi":
        run_multi_session_demo(num_sessions=args.sessions)


if __name__ == "__main__":
    main()
