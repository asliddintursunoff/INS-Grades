/**
 * Telegram Bot Service for INS grades
 * Powered by asliddin_tursunoff
 * Interacts via internal REST API
 */
import dotenv from 'dotenv';
dotenv.config();

export class BackendClient {
  private baseUrl: string;
  private internalKey: string;

  constructor(baseUrl: string, internalKey: string) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
    this.internalKey = internalKey;
  }

  private async request(endpoint: string, options: RequestInit = {}) {
    const headers = {
      'Content-Type': 'application/json',
      'X-Internal-Key': this.internalKey,
      ...(options.headers || {}),
    };

    const url = `${this.baseUrl}${endpoint}`;
    const res = await fetch(url, { ...options, headers });
    if (!res.ok) {
      let errText = '';
      try {
        const json = await res.json();
        errText = json.error || JSON.stringify(json);
      } catch {
        errText = await res.text();
      }
      throw new Error(`API Error [${res.status}]: ${errText}`);
    }
    return res.json();
  }

  async getMe(telegramId: number) {
    return this.request(`/api/auth/me/${telegramId}`);
  }

  async linkStudent(studentId: string, telegramId: number, telegramUsername?: string) {
    return this.request('/api/auth/link/', {
      method: 'POST',
      body: JSON.stringify({
        student_id: studentId,
        telegram_id: telegramId,
        telegram_username: telegramUsername || '',
      }),
    });
  }

  async getTimetable(telegramId: number) {
    return this.request(`/api/students/${telegramId}/timetable/`);
  }

  async getUpcomingNotifications() {
    return this.request('/api/internal/upcoming-sessions/');
  }

  async markNotificationSent(telegramId: number, sessionId: number) {
    return this.request('/api/internal/upcoming-sessions/mark-sent/', {
      method: 'POST',
      body: JSON.stringify({
        telegram_id: telegramId,
        session_id: sessionId,
      }),
    });
  }
}

export class TelegramBotService {
  private botToken: string;
  private apiClient: BackendClient;
  private isRunning = false;
  private offset = 0;
  private appUrl: string;

  constructor(botToken: string, apiUrl: string, internalKey: string, appUrl: string) {
    this.botToken = botToken;
    this.apiClient = new BackendClient(apiUrl, internalKey);
    this.appUrl = appUrl;
  }

  private async callTg(method: string, payload: any = {}) {
    try {
      const res = await fetch(`https://api.telegram.org/bot${this.botToken}/${method}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      return await res.json();
    } catch (err: any) {
      console.warn(`[TelegramBot] callTg ${method} error:`, err.message);
      return { ok: false, error: err.message };
    }
  }

  public async start() {
    if (!this.botToken || this.botToken.includes('MY_BOT_TOKEN')) {
      console.warn('[TelegramBot] No valid TELEGRAM_BOT_TOKEN provided. Bot is paused.');
      return;
    }

    console.log('[TelegramBot] Starting INS grades bot service and scheduler...');
    this.isRunning = true;

    // Set Menu Button in Telegram client
    if (this.appUrl) {
      await this.callTg('setChatMenuButton', {
        menu_button: {
          type: 'web_app',
          text: '📱 INS grades App',
          web_app: { url: this.appUrl },
        },
      });
    }

    // Start background polling loop
    this.pollUpdates();

    // Check notifications every 30 seconds
    setInterval(() => this.checkUpcomingNotifications(), 30000);
  }

  private getPersistentKeyboard() {
    return {
      keyboard: [
        [
          { text: '📱 Open INS grades', web_app: { url: this.appUrl } },
          { text: '📅 Today' },
        ],
        [
          { text: '📆 Full Week' },
          { text: '🔄 Make-up Slot' },
        ],
        [
          { text: '👤 My Profile' },
          { text: '👨‍💼 Admin Help' },
        ],
      ],
      resize_keyboard: true,
      persistent: true,
    };
  }

  private async pollUpdates() {
    while (this.isRunning) {
      try {
        const data = await this.callTg('getUpdates', {
          offset: this.offset,
          timeout: 20,
          allowed_updates: ['message', 'callback_query'],
        });

        if (data.ok && Array.isArray(data.result)) {
          for (const update of data.result) {
            this.offset = update.update_id + 1;
            if (update.message) {
              await this.handleMessage(update.message);
            } else if (update.callback_query) {
              await this.handleCallback(update.callback_query);
            }
          }
        }
      } catch (err: any) {
        console.warn('[TelegramBot] Polling loop error:', err.message);
        await new Promise((r) => setTimeout(r, 3000));
      }
    }
  }

  private async handleCallback(cq: any) {
    const chatId = cq.message?.chat?.id;
    const fromId = cq.from?.id;
    const data = cq.data;

    await this.callTg('answerCallbackQuery', { callback_query_id: cq.id });

    if (!chatId || !fromId) return;

    if (data === 'action_today') {
      await this.sendTodayClasses(chatId, fromId);
    } else if (data === 'action_week') {
      await this.sendTimetable(chatId, fromId);
    } else if (data === 'action_makeup') {
      await this.sendMakeupInfo(chatId);
    } else if (data === 'action_profile') {
      await this.sendProfile(chatId, fromId);
    }
  }

  private async handleMessage(msg: any) {
    const chatId = msg.chat?.id;
    const fromId = msg.from?.id;
    const username = msg.from?.username || '';
    const rawText = (msg.text || '').trim();
    const text = rawText.toLowerCase();

    if (!chatId || !fromId) return;

    // 1. Handle /start command
    if (text.startsWith('/start')) {
      const parts = rawText.split(' ');
      if (parts.length > 1 && parts[1]) {
        await this.tryLinkStudent(chatId, fromId, username, parts[1].trim());
        return;
      }

      // Check if user is already saved in database
      try {
        const authCheck = await this.apiClient.getMe(fromId);
        if (authCheck.found && authCheck.student) {
          const student = authCheck.student;
          // System knows who user is automatically!
          await this.callTg('sendMessage', {
            chat_id: chatId,
            text:
              `🎓 <b>Welcome back to INS grades, ${student.full_name}!</b>\n\n` +
              `🆔 <b>Student ID:</b> <code>${student.student_id}</code>\n` +
              `🏛 <b>Group:</b> <code>${student.group_name}</code>\n` +
              `📚 <b>Academic Year:</b> Year ${student.year_of_study || 2}\n` +
              `✨ <i>powered by @asliddin_tursunoff</i>\n\n` +
              `Tap <b>"📱 Open INS grades"</b> to manage your timetable, switch to upcoming make-up slots, or register retakes.`,
            parse_mode: 'HTML',
            reply_markup: {
              inline_keyboard: [
                [{ text: '📱 Open INS grades', web_app: { url: this.appUrl } }],
                [
                  { text: '📅 Today', callback_data: 'action_today' },
                  { text: '📆 Full Week', callback_data: 'action_week' },
                ],
                [
                  { text: '🔄 Make-up Slot', callback_data: 'action_makeup' },
                  { text: '👤 My Profile', callback_data: 'action_profile' },
                ],
              ],
            },
          });

          // Also deliver persistent mobile reply buttons
          await this.callTg('sendMessage', {
            chat_id: chatId,
            text: `👇 Quick Navigation Menu:`,
            reply_markup: this.getPersistentKeyboard(),
          });
          return;
        }
      } catch (err) {
        // Continue to unlinked prompt
      }

      // Not linked yet: Prompt for Student ID clearly
      await this.callTg('sendMessage', {
        chat_id: chatId,
        text:
          `👋 <b>Welcome to INS grades!</b>\n` +
          `<i>powered by @asliddin_tursunoff</i>\n\n` +
          `Your Telegram ID is not connected yet.\n\n` +
          `👉 Please send your <b>Student ID</b> (e.g. <code>U2410252</code>) to authenticate immediately.\n\n` +
          `If you do not have an account in the system, please contact admin:\n` +
          `👨‍💼 Admin: <b>@asliddin_tursunoff</b>`,
        parse_mode: 'HTML',
      });
      return;
    }

    // 2. Button: Today's classes
    if (text === '📅 today' || text === 'today' || text === 'bugun') {
      await this.sendTodayClasses(chatId, fromId);
      return;
    }

    // 3. Button: Full week timetable
    if (text === '📆 full week' || text === 'full week' || text === 'timetable' || text === 'jadval') {
      await this.sendTimetable(chatId, fromId);
      return;
    }

    // 4. Button: Make-up Slot info
    if (text === '🔄 make-up slot' || text.includes('make-up') || text.includes('switch')) {
      await this.sendMakeupInfo(chatId);
      return;
    }

    // 5. Button: My Profile
    if (text === '👤 my profile' || text === 'profile' || text === 'profil') {
      await this.sendProfile(chatId, fromId);
      return;
    }

    // 6. Button: Admin Help
    if (text === '👨‍💼 admin help' || text.includes('admin') || text.includes('help')) {
      await this.callTg('sendMessage', {
        chat_id: chatId,
        text:
          `👨‍💼 <b>INS grades Administrator Support</b>\n\n` +
          `Need help linking your Student ID, fixing conflicts, or requesting course changes?\n\n` +
          `Direct telegram: <b>@asliddin_tursunoff</b>\n\n` +
          `<i>powered by @asliddin_tursunoff</i>`,
        parse_mode: 'HTML',
      });
      return;
    }

    // 7. If text looks like a Student ID (e.g. U2410252, U2310111, etc.)
    if (/^[A-Za-z0-9_-]{4,20}$/.test(rawText)) {
      await this.tryLinkStudent(chatId, fromId, username, rawText);
      return;
    }

    // Default guidance
    await this.callTg('sendMessage', {
      chat_id: chatId,
      text:
        `💡 <b>How to use INS grades bot:</b>\n\n` +
        `• Send your <b>Student ID</b> (e.g. <code>U2410252</code>) to connect.\n` +
        `• Tap <b>"📅 Today"</b> to see today's lessons.\n` +
        `• Tap <b>"📆 Full Week"</b> to view your weekly timetable.\n` +
        `• Tap <b>"🔄 Make-up Slot"</b> for one-time missed class switches.\n\n` +
        `Questions? Message admin <b>@asliddin_tursunoff</b>`,
      parse_mode: 'HTML',
      reply_markup: this.getPersistentKeyboard(),
    });
  }

  private async tryLinkStudent(chatId: number, fromId: number, username: string, studentId: string) {
    try {
      const res = await this.apiClient.linkStudent(studentId, fromId, username);
      if (res.success) {
        // Recognized in DB: show profile and mini app button!
        await this.callTg('sendMessage', {
          chat_id: chatId,
          text:
            `✅ <b>Welcome, ${res.full_name}!</b>\n\n` +
            `Your student account is now connected:\n` +
            `🆔 <b>Student ID:</b> <code>${res.student_id}</code>\n` +
            `🏛 <b>Group:</b> <code>${res.group_name}</code>\n` +
            `📚 <b>Academic Year:</b> Year ${res.year_of_study || 2}\n` +
            `✨ <i>powered by @asliddin_tursunoff</i>\n\n` +
            `Tap <b>"📱 Open INS grades"</b> below to start:`,
          parse_mode: 'HTML',
          reply_markup: {
            inline_keyboard: [
              [{ text: '📱 Open INS grades', web_app: { url: this.appUrl } }],
            ],
          },
        });

        // Set persistent mobile keyboard
        await this.callTg('sendMessage', {
          chat_id: chatId,
          text: `Navigation ready! Use the buttons below:`,
          reply_markup: this.getPersistentKeyboard(),
        });
      }
    } catch (err: any) {
      // Not in DB: instruct user to talk with admin @asliddin_tursunoff
      await this.callTg('sendMessage', {
        chat_id: chatId,
        text:
          `❌ <b>Student ID "${studentId}" was not found in the database.</b>\n\n` +
          `Please contact the system administrator to add your student record:\n\n` +
          `👨‍💼 Admin: <b>@asliddin_tursunoff</b>\n\n` +
          `<i>powered by @asliddin_tursunoff</i>`,
        parse_mode: 'HTML',
      });
    }
  }

  private async sendTodayClasses(chatId: number, fromId: number) {
    try {
      const res = await this.apiClient.getTimetable(fromId);
      const schedule = res.schedule || [];

      const now = new Date();
      let dayOfWeek = now.getDay(); // 0 is Sunday, 1 is Monday...
      if (dayOfWeek === 0) dayOfWeek = 7;

      const todaySlots = schedule.filter((s: any) => s.day_of_week === dayOfWeek);

      const dayNames = ['', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
      const todayName = dayNames[dayOfWeek] || 'Today';

      if (todaySlots.length === 0) {
        await this.callTg('sendMessage', {
          chat_id: chatId,
          text:
            `🎉 <b>No classes scheduled for today (${todayName})!</b>\n\n` +
            `You can rest or use the time to study. Check <b>"📆 Full Week"</b> to see upcoming lessons.`,
          parse_mode: 'HTML',
        });
        return;
      }

      let text = `📅 <b>Today's Classes (${todayName})</b>\n👤 ${res.student_name || res.group_name}\n\n`;

      for (const slot of todaySlots) {
        const sessionBadge = slot.total_sessions && slot.total_sessions > 1
          ? ` [Session ${slot.session_number}/${slot.total_sessions}]`
          : '';
        const makeupBadge = slot.is_changed ? ` 🔄 (One-time make-up: ${slot.actual_group})` : '';

        text +=
          `⏰ <b>${slot.start_time} - ${slot.end_time}</b>\n` +
          `📘 <b>${slot.subject_full}</b> (${slot.subject_short})${sessionBadge}${makeupBadge}\n` +
          `👨‍🏫 ${slot.professor} | 🏫 Room: <b>${slot.room}</b>\n\n`;
      }

      await this.callTg('sendMessage', {
        chat_id: chatId,
        text,
        parse_mode: 'HTML',
        reply_markup: {
          inline_keyboard: [
            [{ text: '📱 Open INS grades', web_app: { url: this.appUrl } }],
          ],
        },
      });
    } catch {
      await this.sendUnlinkedMessage(chatId);
    }
  }

  private async sendTimetable(chatId: number, fromId: number) {
    try {
      const res = await this.apiClient.getTimetable(fromId);
      const schedule = res.schedule || [];

      if (schedule.length === 0) {
        await this.callTg('sendMessage', {
          chat_id: chatId,
          text: `📅 No active classes currently scheduled for your profile.`,
        });
        return;
      }

      let message = `📋 <b>INS grades Timetable</b>\n👤 <b>${res.student_name}</b> (${res.group_name})\n`;
      let currentDay = '';

      for (const item of schedule) {
        if (item.day_name !== currentDay) {
          currentDay = item.day_name;
          message += `\n🗓 <b>${currentDay.toUpperCase()}</b>\n`;
        }

        const overrideTag = item.is_changed
          ? ` 🔄 <i>(one-time make-up: ${item.actual_group})</i>`
          : '';

        const sessionTag = item.total_sessions && item.total_sessions > 1
          ? ` [Session ${item.session_number}/${item.total_sessions}]`
          : '';

        message +=
          `• <b>${item.start_time} - ${item.end_time}</b>: ${item.subject_full} (${item.subject_short})${sessionTag}${overrideTag}\n` +
          `   👨‍🏫 ${item.professor} | 🏫 Room: ${item.room}\n`;
      }

      message += `\n<i>powered by @asliddin_tursunoff</i>`;

      await this.callTg('sendMessage', {
        chat_id: chatId,
        text: message,
        parse_mode: 'HTML',
        reply_markup: {
          inline_keyboard: [
            [{ text: '📱 Open INS grades App', web_app: { url: this.appUrl } }],
          ],
        },
      });
    } catch {
      await this.sendUnlinkedMessage(chatId);
    }
  }

  private async sendMakeupInfo(chatId: number) {
    await this.callTg('sendMessage', {
      chat_id: chatId,
      text:
        `🔄 <b>One-Time Make-up Lesson Switching</b>\n\n` +
        `• Missed a class this week or have an upcoming conflict?\n` +
        `• You can search for an <b>upcoming lesson</b> from another group to attend as a make-up.\n` +
        `• <b>One-Time Rule:</b> The switch is active for <b>this week only</b>. Next week, your schedule automatically returns to your regular primary group!\n\n` +
        `Tap below to open INS grades and choose your make-up slot:`,
      parse_mode: 'HTML',
      reply_markup: {
        inline_keyboard: [
          [{ text: '⚡ Choose Upcoming Make-up Slot', web_app: { url: this.appUrl } }],
        ],
      },
    });
  }

  private async sendProfile(chatId: number, fromId: number) {
    try {
      const auth = await this.apiClient.getMe(fromId);
      if (auth.found && auth.student) {
        const s = auth.student;
        await this.callTg('sendMessage', {
          chat_id: chatId,
          text:
            `👤 <b>Your INS grades Profile</b>\n\n` +
            `• <b>Full Name:</b> ${s.full_name}\n` +
            `• <b>Student ID:</b> <code>${s.student_id}</code>\n` +
            `• <b>Primary Group:</b> <code>${s.group_name}</code>\n` +
            `• <b>Academic Level:</b> Year ${s.year_of_study || 2}\n` +
            `• <b>Telegram ID:</b> <code>${fromId}</code>\n\n` +
            `👨‍💼 Admin: <b>@asliddin_tursunoff</b>\n` +
            `<i>powered by @asliddin_tursunoff</i>`,
          parse_mode: 'HTML',
          reply_markup: {
            inline_keyboard: [
              [{ text: '📱 Open INS grades', web_app: { url: this.appUrl } }],
            ],
          },
        });
        return;
      }
    } catch {
      // not linked
    }
    await this.sendUnlinkedMessage(chatId);
  }

  private async sendUnlinkedMessage(chatId: number) {
    await this.callTg('sendMessage', {
      chat_id: chatId,
      text:
        `❌ <b>Account Not Linked</b>\n\n` +
        `Please send your <b>Student ID</b> (e.g. <code>U2410252</code>) to connect your schedule.\n\n` +
        `Need help? Talk with admin: <b>@asliddin_tursunoff</b>\n` +
        `<i>powered by @asliddin_tursunoff</i>`,
      parse_mode: 'HTML',
    });
  }

  private async checkUpcomingNotifications() {
    try {
      const data = await this.apiClient.getUpcomingNotifications();
      const notifications = data.notifications || [];

      for (const n of notifications) {
        const text =
          `⏰ <b>INS grades Reminder: Class starts in ${n.minutes_before} min!</b>\n\n` +
          `📘 <b>${n.subject_full}</b> (${n.subject_short})\n` +
          `👨‍🏫 ${n.professor}\n` +
          `🏫 Room: <b>${n.room}</b>\n` +
          `🕐 Time: <b>${n.start_time} - ${n.end_time}</b>\n\n` +
          `<i>powered by @asliddin_tursunoff</i>`;

        const sentRes = await this.callTg('sendMessage', {
          chat_id: n.telegram_id,
          text,
          parse_mode: 'HTML',
          reply_markup: {
            inline_keyboard: [
              [{ text: '📱 View Timetable', web_app: { url: this.appUrl } }],
            ],
          },
        });

        if (sentRes.ok) {
          await this.apiClient.markNotificationSent(n.telegram_id, n.session_id);
          console.log(`[TelegramBot] Sent reminder notification to ${n.telegram_id} for session ${n.session_id}`);
        }
      }
    } catch (err: any) {
      // Silent catch for notification cycle
    }
  }
}
