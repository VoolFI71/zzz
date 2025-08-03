import os
import asyncio
import aiohttp
from yookassa import Configuration, Payment

AUTH_CODE = os.getenv("AUTH_CODE")
urlupdate = "http://fastapi:8080/giveconfig"

async def check_payment_status(payment_id, bot, user_id, description, message_id):
    i = 0
    while i < 46:
        await asyncio.sleep(10) 
        try: 
            data = {}
            if description == "1m":
                data["time"] = 1 * 31
            elif description == "3m":
                data["time"] = 3 * 31
            data["id"] = str(user_id)

            payment = Payment.find_one(str(payment_id))
        
            if payment.status == "succeeded" and payment.paid:
                await bot.send_message(
                    chat_id=user_id,
                    text="Успешно! Ваш платеж был подтвержден."
                )
                data["auth"] = AUTH_CODE
                async with aiohttp.ClientSession() as session:
                    try:
                        async with session.post(urlupdate, json=data) as response:
                            if response.status == 200:
                                await bot.send_message(user_id, "Конфиг для подключения можно найти в личном кабинете.")
                            elif response.status == 409:
                                await bot.send_message(user_id, "Ошибка при получении конфига. Свободных конфигов нет. Обратитесь в поддержку.")
                            else:
                                await bot.send_message(user_id, "Ошибка при получении конфига. Обратитесь в поддержку. Номер ошибки 1.")
                    except Exception as e:
                        await bot.send_message(user_id, "Ошибка при получении конфига. Обратитесь в поддержку. Номер ошибки 2.")
                        print(f"Exception occurred: {e}")

                await bot.delete_message(chat_id=user_id, message_id=message_id)
                break
                
            elif payment.status == "canceled":
                await bot.send_message(
                    chat_id=user_id,
                    text="Платеж не был подтвержден. Попробуйте снова."
                )
                await bot.delete_message(chat_id=user_id, message_id=message_id)

            elif payment.status == "pending":
                pass
                # await bot.send_message(
                #     chat_id=user_id,
                #     text="Ожидание оплаты."
                # )
        except Exception as e:
            print(e)
        i+=1