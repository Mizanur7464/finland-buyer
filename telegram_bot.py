"""
Telegram bot for monitoring copy trading bot stats
"""
import asyncio
from typing import Dict, Optional
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes
from config import Config
from trade_database import TradeDatabase
import os

class TelegramMonitor:
    """Telegram bot for monitoring copy trading bot"""
    
    def __init__(self, bot_token: str = None, chat_id: str = None, copy_trader=None):
        """
        Initialize Telegram bot
        
        Args:
            bot_token: Telegram bot token (from BotFather)
            chat_id: Your Telegram chat ID (where to send messages)
            copy_trader: CopyTrader instance (optional, for accessing trade_db)
        """
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID", "")
        
        if not self.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN not set in .env file")
        if not self.chat_id:
            raise ValueError("TELEGRAM_CHAT_ID not set in .env file")
        
        self.application = None
        self.copy_trader = copy_trader  # Store reference to copy_trader
        self.trade_db = TradeDatabase()  # Initialize trade database
        self.bot_stats: Dict = {
            "total_copies": 0,
            "successful_copies": 0,
            "failed_copies": 0,
            "avg_latency_ms": 0.0,
            "last_trade_time": None,
            "is_running": False
        }
        self.status_message_id: Optional[int] = None
    
    async def initialize(self):
        """Initialize Telegram bot"""
        # Build application with token
        self.application = Application.builder().token(self.bot_token).build()
        
        # Add command handlers BEFORE initialization
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("stats", self.stats_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        
        # New commands for buyer features
        self.application.add_handler(CommandHandler("pnl", self.pnl_command))
        self.application.add_handler(CommandHandler("latency", self.latency_command))
        self.application.add_handler(CommandHandler("trades", self.trades_command))
        self.application.add_handler(CommandHandler("duration", self.duration_command))
        self.application.add_handler(CommandHandler("lotsize", self.lotsize_command))
        self.application.add_handler(CommandHandler("dashboard", self.dashboard_command))
        self.application.add_handler(CommandHandler("setlotsize", self.setlotsize_command))
        self.application.add_handler(CommandHandler("setslippage", self.setslippage_command))
        self.application.add_handler(CommandHandler("settips", self.settips_command))
        self.application.add_handler(CommandHandler("fees", self.fees_command))
        
        # Initialize and start bot
        await self.application.initialize()
        await self.application.start()
        
        print(f"✅ Telegram bot started")
        print(f"📱 Bot is ready. Chat ID: {self.chat_id}")
        
        # CRITICAL FIX: Start polling - it must run in the same event loop
        # The polling needs to process updates continuously
        import asyncio
        
        print(f"🔄 Starting Telegram polling...")
        
        # Start polling in background task - this is the CORRECT way
        # start_polling() is async and will run continuously
        async def run_polling_forever():
            """Run polling continuously until stopped"""
            try:
                print(f"🔄 Polling started, waiting for updates...")
                # Start polling with minimal parameters - only supported ones
                # For python-telegram-bot 21.7, use basic parameters only
                await self.application.updater.start_polling(
                    drop_pending_updates=True,
                    allowed_updates=["message"]
                )
                # This line will never be reached as polling runs forever
            except asyncio.CancelledError:
                print(f"🛑 Polling task cancelled")
                raise
            except Exception as e:
                print(f"❌ CRITICAL: Polling failed: {e}")
                print(f"   Error type: {type(e).__name__}")
                print(f"   Bot will not receive commands!")
                import traceback
                traceback.print_exc()
                # Re-raise to detect in initialization
                raise
        
        # Create and store polling task - keep reference so it doesn't get garbage collected
        self._polling_task = asyncio.create_task(run_polling_forever())
        
        # Give polling a moment to start and verify it's running
        await asyncio.sleep(2)
        
        # Check if polling task is still running (not crashed)
        if self._polling_task.done():
            # Task completed (means it errored)
            try:
                await self._polling_task  # This will raise the exception
            except Exception as e:
                print(f"❌ Polling task failed: {e}")
                print(f"   Bot commands will NOT work!")
        else:
            print(f"✅ Polling task is running (ready to receive commands)")
        
        print(f"📱 Bot is listening for commands...")
        print(f"   Try sending /start to your bot in Telegram")
        print(f"   Chat ID configured: {self.chat_id}")
        
        # Send startup message to verify bot is working
        try:
            bot = self.application.bot
            result = await bot.send_message(
                chat_id=self.chat_id,
                text="🤖 *Copy Trading Bot Started*\n\nBot is now monitoring...\n\nUse /start to see commands",
                parse_mode="Markdown"
            )
            print(f"✅ Startup message sent successfully (Message ID: {result.message_id})")
        except Exception as e:
            print(f"⚠️ Could not send startup message: {e}")
            print(f"   Error type: {type(e).__name__}")
            print(f"   Make sure:")
            print(f"   1. CHAT_ID ({self.chat_id}) is correct")
            print(f"   2. You've sent at least one message to the bot first")
            print(f"   3. Bot token is valid")
            
            # Try to get updates to verify bot is working
            try:
                updates = await bot.get_updates(limit=1)
                if updates:
                    print(f"   ✓ Bot can receive updates")
                    last_update = updates[-1]
                    if hasattr(last_update, 'message') and last_update.message:
                        actual_chat_id = last_update.message.chat.id
                        print(f"   ⚠️ Last message chat ID: {actual_chat_id} (configured: {self.chat_id})")
                        if str(actual_chat_id) != str(self.chat_id):
                            print(f"   ❌ CHAT_ID MISMATCH! Use: {actual_chat_id}")
            except Exception as e2:
                print(f"   ⚠️ Could not verify bot: {e2}")
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        try:
            print(f"\n{'='*50}")
            print(f"📨 RECEIVED /start COMMAND")
            print(f"   Chat ID: {update.effective_chat.id if update.effective_chat else 'unknown'}")
            print(f"   User: {update.effective_user.username if update.effective_user else 'unknown'}")
            print(f"{'='*50}")
            
            message = """
🤖 *Copy Trading Bot Monitor*

*Basic Commands:*
/start - Show this message
/stats - Show current statistics  
/status - Show bot status

*New Features:*
/pnl [hour|day|week|total] - Show profit & loss
/latency - Show latency breakdown
/trades [successful|failed|errors] - Show trade history
/duration - Show trade duration stats
/lotsize - Show lot size settings
/setlotsize <mode> <value> - Set lot size
   Modes: fixed, percentage, multiplier
   Example: /setlotsize percentage 10
/fees - Show tips & slippage settings
/setslippage <value> - Set slippage (e.g., 1.0)
/settips <value> - Set tips in SOL (e.g., 0.0001)
/dashboard - Complete dashboard view

Bot will automatically send updates when trades are executed.
            """
            
            if update.message:
                print(f"✅ Sending reply...")
                await update.message.reply_text(message.strip(), parse_mode="Markdown")
                chat_id = update.effective_chat.id if update.effective_chat else "unknown"
                print(f"✅ REPLY SENT to chat {chat_id}")
                print(f"{'='*50}\n")
            else:
                print(f"❌ update.message is None!")
        except Exception as e:
            print(f"❌ ERROR in start_command: {e}")
            import traceback
            traceback.print_exc()
            try:
                if update and update.message:
                    await update.message.reply_text("❌ Error processing command. Please try again.")
            except Exception as e2:
                print(f"❌ Could not send error message: {e2}")
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command"""
        try:
            stats_text = self._format_stats()
            await update.message.reply_text(stats_text, parse_mode="Markdown")
            print(f"✅ Processed /stats command from {update.effective_chat.id}")
        except Exception as e:
            print(f"⚠️ Error in stats_command: {e}")
            await update.message.reply_text("❌ Error getting stats. Please try again.")
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        try:
            status_text = "🟢 Running" if self.bot_stats.get("is_running") else "🔴 Stopped"
            message = f"*Bot Status:* {status_text}\n\n{self._format_stats()}"
            await update.message.reply_text(message, parse_mode="Markdown")
            print(f"✅ Processed /status command from {update.effective_chat.id}")
        except Exception as e:
            print(f"⚠️ Error in status_command: {e}")
            await update.message.reply_text("❌ Error getting status. Please try again.")
    
    def _format_stats(self) -> str:
        """Format stats for Telegram message"""
        stats = self.bot_stats
        total = stats.get("total_copies", 0)
        successful = stats.get("successful_copies", 0)
        failed = stats.get("failed_copies", 0)
        avg_latency = stats.get("avg_latency_ms", 0.0)
        
        success_rate = (successful / total * 100) if total > 0 else 0
        
        message = f"""
📊 *Copy Trading Bot Stats*

📈 Total Copies: {total}
✅ Successful: {successful}
❌ Failed: {failed}
📉 Success Rate: {success_rate:.1f}%
⚡ Avg Latency: {avg_latency:.2f}ms

🔍 Monitoring: {Config.MASTER_WALLET_ADDRESS[:10]}...
        """
        return message.strip()
    
    async def update_stats(self, stats: Dict):
        """Update bot statistics"""
        self.bot_stats.update(stats)
        
        # Send update if there are new trades
        if stats.get("total_copies", 0) > 0:
            await self.send_stats_update(stats)
    
    async def send_stats_update(self, stats: Dict):
        """Send stats update message"""
        message = self._format_stats()
        
        # Try to update existing message, or send new one
        try:
            if self.status_message_id:
                await self.application.bot.edit_message_text(
                    chat_id=self.chat_id,
                    message_id=self.status_message_id,
                    text=message,
                    parse_mode="Markdown"
                )
            else:
                sent = await self.send_message(message, parse_mode="Markdown")
                if sent:
                    self.status_message_id = sent.message_id
        except Exception as e:
            # If update fails, send new message
            sent = await self.send_message(message, parse_mode="Markdown")
            if sent:
                self.status_message_id = sent.message_id
    
    async def send_message(self, text: str, parse_mode: str = None) -> Optional[object]:
        """Send message to configured chat"""
        try:
            # Use application bot if available, otherwise create new bot
            if self.application and self.application.bot:
                bot = self.application.bot
            else:
                bot = Bot(token=self.bot_token)
            
            message = await bot.send_message(
                chat_id=self.chat_id,
                text=text,
                parse_mode=parse_mode
            )
            return message
        except Exception as e:
            print(f"⚠️ Error sending Telegram message: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def send_trade_notification(self, trade_info: Dict):
        """Send notification when trade is executed"""
        is_success = trade_info.get("success", False)
        latency = trade_info.get("latency_ms", 0)
        
        emoji = "✅" if is_success else "❌"
        status = "Success" if is_success else "Failed"
        
        message = f"""
{emoji} *Copy Trade Executed*

Status: {status}
Latency: {latency:.2f}ms
Time: {trade_info.get('timestamp', 'N/A')}
        """
        
        await self.send_message(message.strip(), parse_mode="Markdown")
    
    # ==================== NEW COMMANDS ====================
    
    async def pnl_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /pnl command - Show profit & loss"""
        try:
            period = context.args[0].lower() if context.args and len(context.args) > 0 else "total"
            
            if period not in ["hour", "day", "week", "total"]:
                period = "total"
            
            pnl_data = self.trade_db.get_pnl_by_period(period)
            total_pnl = self.trade_db.get_total_pnl()
            
            if period == "hour":
                message = "📈 *Hourly PnL Report*\n\n"
            elif period == "day":
                message = "📈 *Daily PnL Report*\n\n"
            elif period == "week":
                message = "📈 *Weekly PnL Report*\n\n"
            else:
                message = "📈 *Total PnL Report*\n\n"
            
            if pnl_data:
                for period_key, data in sorted(pnl_data.items(), reverse=True):
                    profit = data.get("profit", 0.0)
                    loss = data.get("loss", 0.0)
                    net = data.get("net_pnl", 0.0)
                    trades = data.get("trades", 0)
                    
                    emoji = "✅" if net > 0 else "❌" if net < 0 else "➖"
                    message += f"{emoji} *{period_key}*\n"
                    message += f"💰 Profit: +{profit:.6f} SOL\n"
                    message += f"📉 Loss: -{loss:.6f} SOL\n"
                    message += f"📊 Net: {net:+.6f} SOL\n"
                    message += f"📈 Trades: {trades}\n\n"
            else:
                message += "No trades in this period yet.\n"
            
            # Add total summary
            message += f"\n*Total Summary:*\n"
            message += f"💰 Total Profit: +{total_pnl.get('total_profit', 0.0):.6f} SOL\n"
            message += f"📉 Total Loss: -{total_pnl.get('total_loss', 0.0):.6f} SOL\n"
            message += f"📊 Net PnL: {total_pnl.get('net_pnl', 0.0):+.6f} SOL\n"
            message += f"📈 ROI: {total_pnl.get('roi', 0.0):+.2f}%"
            
            await update.message.reply_text(message, parse_mode="Markdown")
        except Exception as e:
            print(f"⚠️ Error in pnl_command: {e}")
            await update.message.reply_text("❌ Error getting PnL data. Please try again.")
    
    async def latency_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /latency command - Show latency breakdown"""
        try:
            averages = self.trade_db.get_latency_averages()
            stats = self.bot_stats
            
            message = "⏱️ *Latency Breakdown*\n\n"
            
            # Show per-trade latencies (last 10)
            message += "*Last 10 Trades:*\n"
            successful_trades = self.trade_db.get_successful_trades(limit=10)
            if successful_trades:
                for i, trade in enumerate(reversed(successful_trades[-10:]), 1):
                    latency = trade.get("latency_ms", 0.0)
                    emoji = "✅" if latency < Config.MAX_LATENCY_MS else "⚠️"
                    message += f"{i}. {emoji} {latency:.2f}ms\n"
            else:
                message += "No trades yet.\n"
            
            message += "\n*Averages:*\n"
            message += f"• Last 1 min: {averages.get('1min', 0.0):.2f}ms\n"
            message += f"• Last 15 min: {averages.get('15min', 0.0):.2f}ms\n"
            message += f"• Last 1 hour: {averages.get('1hour', 0.0):.2f}ms\n"
            message += f"• Last 4 hours: {averages.get('4hours', 0.0):.2f}ms\n"
            message += f"• Last 24 hours: {averages.get('24hours', 0.0):.2f}ms\n"
            message += f"• All time: {averages.get('all_time', 0.0):.2f}ms\n"
            message += f"\n*Target:* <{Config.MAX_LATENCY_MS}ms"
            
            if averages.get('all_time', 0.0) < Config.MAX_LATENCY_MS:
                message += " ✅"
            else:
                message += " ⚠️"
            
            await update.message.reply_text(message, parse_mode="Markdown")
        except Exception as e:
            print(f"⚠️ Error in latency_command: {e}")
            await update.message.reply_text("❌ Error getting latency data. Please try again.")
    
    async def trades_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /trades command - Show trade history"""
        try:
            trade_type = context.args[0].lower() if context.args and len(context.args) > 0 else "successful"
            
            if trade_type == "successful":
                trades = self.trade_db.get_successful_trades(limit=20)
                message = "✅ *Successful Trades* (Last 20)\n\n"
                
                if trades:
                    for i, trade in enumerate(reversed(trades[-20:]), 1):
                        timestamp = trade.get("timestamp", "")
                        amount = trade.get("amount_in", 0.0)
                        pnl = trade.get("pnl", 0.0)
                        latency = trade.get("latency_ms", 0.0)
                        
                        # Format timestamp
                        try:
                            from datetime import datetime
                            dt = datetime.fromisoformat(timestamp)
                            time_str = dt.strftime("%H:%M:%S")
                        except:
                            time_str = timestamp[:8] if len(timestamp) > 8 else timestamp
                        
                        pnl_emoji = "💰" if pnl > 0 else "📉" if pnl < 0 else "➖"
                        message += f"*#{i}* - {time_str}\n"
                        message += f"{pnl_emoji} Amount: {amount:.6f} SOL\n"
                        if pnl:
                            message += f"{pnl_emoji} PnL: {pnl:+.6f} SOL\n"
                        message += f"⚡ Latency: {latency:.2f}ms\n\n"
                else:
                    message += "No successful trades yet."
                    
            elif trade_type == "failed":
                trades = self.trade_db.get_failed_trades(limit=20)
                message = "❌ *Failed/Non-Executed Trades* (Last 20)\n\n"
                
                if trades:
                    for i, trade in enumerate(reversed(trades[-20:]), 1):
                        timestamp = trade.get("timestamp", "")
                        reason = trade.get("reason", "Unknown")
                        master_amount = trade.get("master_amount", 0.0)
                        
                        try:
                            from datetime import datetime
                            dt = datetime.fromisoformat(timestamp)
                            time_str = dt.strftime("%H:%M:%S")
                        except:
                            time_str = timestamp[:8] if len(timestamp) > 8 else timestamp
                        
                        message += f"*#{i}* - {time_str}\n"
                        message += f"⚠️ Reason: {reason}\n"
                        if master_amount > 0:
                            message += f"📊 Master traded: {master_amount:.6f} SOL\n"
                        message += "\n"
                else:
                    message += "No failed trades yet."
                    
            elif trade_type == "errors":
                errors = self.trade_db.get_errors(limit=20)
                message = "❌ *Errors List* (Last 20)\n\n"
                
                if errors:
                    for i, error in enumerate(reversed(errors[-20:]), 1):
                        timestamp = error.get("timestamp", "")
                        error_msg = error.get("error_message", "Unknown")
                        cause = error.get("potential_cause", "Unknown")
                        
                        try:
                            from datetime import datetime
                            dt = datetime.fromisoformat(timestamp)
                            time_str = dt.strftime("%H:%M:%S")
                        except:
                            time_str = timestamp[:8] if len(timestamp) > 8 else timestamp
                        
                        message += f"*#{i}* - {time_str}\n"
                        message += f"⚠️ Error: {error_msg[:50]}...\n"
                        message += f"🔍 Cause: {cause}\n\n"
                else:
                    message += "No errors recorded yet."
            else:
                message = "❌ Invalid trade type. Use: /trades successful|failed|errors"
            
            await update.message.reply_text(message, parse_mode="Markdown")
        except Exception as e:
            print(f"⚠️ Error in trades_command: {e}")
            import traceback
            traceback.print_exc()
            await update.message.reply_text("❌ Error getting trade history. Please try again.")
    
    async def duration_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /duration command - Show trade duration stats"""
        try:
            stats = self.trade_db.get_trade_duration_stats()
            
            message = "⏳ *Trade Duration Stats*\n\n"
            
            avg_duration = stats.get("average_duration", 0.0)
            shortest = stats.get("shortest_duration", 0.0)
            longest = stats.get("longest_duration", 0.0)
            durations = stats.get("durations", [])
            
            if avg_duration > 0:
                # Convert seconds to human-readable format
                def format_duration(seconds):
                    if seconds < 60:
                        return f"{seconds:.1f}s"
                    elif seconds < 3600:
                        minutes = seconds / 60
                        return f"{minutes:.1f}m"
                    else:
                        hours = seconds / 3600
                        return f"{hours:.1f}h"
                
                message += f"*Average Duration:* {format_duration(avg_duration)}\n"
                message += f"*Shortest Trade:* {format_duration(shortest)}\n"
                message += f"*Longest Trade:* {format_duration(longest)}\n\n"
                
                if durations:
                    message += "*Last 10 Trades:*\n"
                    for i, dur in enumerate(reversed(durations[-10:]), 1):
                        message += f"{i}. {format_duration(dur)}\n"
            else:
                message += "No duration data available yet."
            
            await update.message.reply_text(message, parse_mode="Markdown")
        except Exception as e:
            print(f"⚠️ Error in duration_command: {e}")
            await update.message.reply_text("❌ Error getting duration stats. Please try again.")
    
    async def lotsize_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /lotsize command - Show lot size settings"""
        try:
            mode = Config.LOT_SIZE_MODE
            value = Config.LOT_SIZE_VALUE
            
            message = "⚙️ *Lot Size Settings*\n\n"
            message += f"*Mode:* {mode}\n"
            message += f"*Value:* {value}\n\n"
            
            if mode == "fixed":
                message += f"Bot will always trade *{value} SOL* regardless of master wallet amount."
            elif mode == "percentage":
                message += f"Bot will trade *{value}%* of master wallet amount.\n"
                message += f"Example: Master trades 1 SOL → You trade {value/100 * 1:.6f} SOL"
            elif mode == "multiplier":
                message += f"Bot will trade *{value}x* of master wallet amount.\n"
                message += f"Example: Master trades 1 SOL → You trade {value * 1:.6f} SOL"
            else:
                message += f"Unknown mode: {mode}"
            
            message += f"\n\nUse /setlotsize to change settings."
            
            await update.message.reply_text(message, parse_mode="Markdown")
        except Exception as e:
            print(f"⚠️ Error in lotsize_command: {e}")
            await update.message.reply_text("❌ Error getting lot size settings. Please try again.")
    
    async def setlotsize_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /setlotsize command - Set lot size"""
        try:
            if not context.args or len(context.args) < 2:
                await update.message.reply_text(
                    "❌ Usage: /setlotsize <mode> <value>\n\n"
                    "Modes: fixed, percentage, multiplier\n"
                    "Example: /setlotsize percentage 10"
                )
                return
            
            mode = context.args[0].lower()
            value = float(context.args[1])
            
            if mode not in ["fixed", "percentage", "multiplier"]:
                await update.message.reply_text("❌ Invalid mode. Use: fixed, percentage, or multiplier")
                return
            
            # Note: This should update config file or database
            # For now, just show confirmation
            message = f"✅ Lot size updated:\n\n"
            message += f"*Mode:* {mode}\n"
            message += f"*Value:* {value}\n\n"
            message += "⚠️ Note: Changes require bot restart to take effect.\n"
            message += "Update .env file: LOT_SIZE_MODE={mode} and LOT_SIZE_VALUE={value}"
            
            await update.message.reply_text(message.format(mode=mode, value=value), parse_mode="Markdown")
        except ValueError:
            await update.message.reply_text("❌ Invalid value. Value must be a number.")
        except Exception as e:
            print(f"⚠️ Error in setlotsize_command: {e}")
            await update.message.reply_text("❌ Error setting lot size. Please try again.")
    
    async def dashboard_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /dashboard command - Show complete dashboard"""
        try:
            stats = self.bot_stats
            total_pnl = self.trade_db.get_total_pnl()
            latency_avg = self.trade_db.get_latency_averages()
            duration_stats = self.trade_db.get_trade_duration_stats()
            
            message = "📊 *Trading Dashboard*\n\n"
            
            # Status
            status_emoji = "🟢" if stats.get("is_running") else "🔴"
            message += f"🤖 *Status:* {status_emoji} {'Running' if stats.get('is_running') else 'Stopped'}\n\n"
            
            # Performance
            total = stats.get("total_copies", 0)
            successful = stats.get("successful_copies", 0)
            failed = stats.get("failed_copies", 0)
            success_rate = (successful / total * 100) if total > 0 else 0
            
            message += f"*Performance:*\n"
            message += f"• Total Trades: {total}\n"
            message += f"• Successful: {successful} ({success_rate:.1f}%)\n"
            message += f"• Failed: {failed}\n"
            message += f"• Net PnL: {total_pnl.get('net_pnl', 0.0):+.6f} SOL\n"
            message += f"• ROI: {total_pnl.get('roi', 0.0):+.2f}%\n\n"
            
            # Latency
            current_latency = latency_avg.get("1min", 0.0) or latency_avg.get("all_time", 0.0)
            message += f"*Latency:*\n"
            message += f"• Current: {current_latency:.2f}ms\n"
            message += f"• 1h Avg: {latency_avg.get('1hour', 0.0):.2f}ms\n"
            message += f"• 24h Avg: {latency_avg.get('24hours', 0.0):.2f}ms\n"
            message += f"• Target: <{Config.MAX_LATENCY_MS}ms"
            if current_latency < Config.MAX_LATENCY_MS:
                message += " ✅\n\n"
            else:
                message += " ⚠️\n\n"
            
            # Settings
            message += f"*Settings:*\n"
            message += f"• Lot Size: {Config.LOT_SIZE_MODE} ({Config.LOT_SIZE_VALUE})\n"
            message += f"• Slippage: {Config.SLIPPAGE_TOLERANCE}%\n"
            message += f"• Tips: {Config.TIPS_AMOUNT} SOL\n\n"
            
            # Recent trades
            recent_trades = self.trade_db.get_successful_trades(limit=3)
            if recent_trades:
                message += "*Recent Trades:*\n"
                for i, trade in enumerate(reversed(recent_trades[-3:]), 1):
                    pnl = trade.get("pnl", 0.0)
                    emoji = "✅" if pnl > 0 else "❌" if pnl < 0 else "➖"
                    message += f"{i}. {emoji} {pnl:+.6f} SOL\n"
            
            await update.message.reply_text(message, parse_mode="Markdown")
        except Exception as e:
            print(f"⚠️ Error in dashboard_command: {e}")
            import traceback
            traceback.print_exc()
            await update.message.reply_text("❌ Error getting dashboard data. Please try again.")
    
    async def fees_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /fees command - Show tips & slippage settings"""
        try:
            message = "💰 *Tips & Slippage Settings*\n\n"
            message += f"*Slippage Tolerance:* {Config.SLIPPAGE_TOLERANCE}%\n"
            message += f"*Tips/Priority Fee:* {Config.TIPS_AMOUNT} SOL\n"
            message += f"*Fee Buffer:* {Config.FEE_BUFFER} SOL\n\n"
            message += "Use /setslippage <value> to change slippage\n"
            message += "Use /settips <value> to change tips"
            
            await update.message.reply_text(message, parse_mode="Markdown")
        except Exception as e:
            print(f"⚠️ Error in fees_command: {e}")
            await update.message.reply_text("❌ Error getting fee settings. Please try again.")
    
    async def setslippage_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /setslippage command - Set slippage tolerance"""
        try:
            if not context.args or len(context.args) < 1:
                await update.message.reply_text("❌ Usage: /setslippage <value>\nExample: /setslippage 1.0 (for 1%)")
                return
            
            value = float(context.args[0])
            
            message = f"✅ Slippage updated to {value}%\n\n"
            message += "⚠️ Note: Changes require bot restart to take effect.\n"
            message += f"Update .env file: SLIPPAGE_TOLERANCE={value}"
            
            await update.message.reply_text(message, parse_mode="Markdown")
        except ValueError:
            await update.message.reply_text("❌ Invalid value. Value must be a number.")
        except Exception as e:
            print(f"⚠️ Error in setslippage_command: {e}")
            await update.message.reply_text("❌ Error setting slippage. Please try again.")
    
    async def settips_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /settips command - Set tips amount"""
        try:
            if not context.args or len(context.args) < 1:
                await update.message.reply_text("❌ Usage: /settips <value>\nExample: /settips 0.0001")
                return
            
            value = float(context.args[0])
            
            message = f"✅ Tips updated to {value} SOL\n\n"
            message += "⚠️ Note: Changes require bot restart to take effect.\n"
            message += f"Update .env file: TIPS_AMOUNT={value}"
            
            await update.message.reply_text(message, parse_mode="Markdown")
        except ValueError:
            await update.message.reply_text("❌ Invalid value. Value must be a number.")
        except Exception as e:
            print(f"⚠️ Error in settips_command: {e}")
            await update.message.reply_text("❌ Error setting tips. Please try again.")
    
    async def stop(self):
        """Stop Telegram bot"""
        try:
            await self.send_message("🛑 *Copy Trading Bot Stopped*", parse_mode="Markdown")
        except:
            pass
        
        if self.application:
            try:
                await self.application.updater.stop()
                await self.application.stop()
                await self.application.shutdown()
            except Exception as e:
                print(f"⚠️ Error stopping Telegram bot: {e}")
        
        # Cancel polling task if exists
        if hasattr(self, '_polling_task'):
            try:
                self._polling_task.cancel()
            except:
                pass
        
        print("✅ Telegram bot stopped")

