import asyncio
import aiosqlite

async def main():
    async with aiosqlite.connect("bot.db") as db:
        try:
            await db.execute("ALTER TABLE users ADD COLUMN last_kids_index INTEGER DEFAULT 0")
            await db.commit()
            print("✅ last_kids_index бағаны сәтті қосылды!")
        except Exception as e:
            print("⚠️ Қате немесе баған бұрыннан бар:", e)

asyncio.run(main())
