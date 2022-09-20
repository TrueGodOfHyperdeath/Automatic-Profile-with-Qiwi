
import asyncio
import hashlib

from Crypto.Cipher import DES
from Crypto.Util.Padding import pad, unpad
from glQiwiApi import QiwiWrapper
from telethon import types
import ast
import time
import logging
from io import BytesIO
from telethon.tl import functions
from .. import loader, utils

logger = logging.getLogger(__name__)

try:
    from PIL import Image
except ImportError:
    pil_installed = False
else:
    pil_installed = True


def register(cb):
    cb(AutoProfileMod())


@loader.tds
class AutoProfileMod(loader.Module):
    """Автоматический профиль работающий с киви от @Deltatale_admin"""
    strings = {"name": "Automatic Profile with Qiwi",
               "missing_pil": "<b>У вас не установлен Pillow</b>",
               "missing_pfp": "<b>У вас нет изображения профиля для поворота</b>",
               "invalid_args": "<b>Отсутствуют параметры, прочтите документацию</b>",
               "invalid_degrees": "<b>Неверное количество градусов для поворота, пожалуйста, прочтите документацию</b>",
               "invalid_delete": "<b>Укажите, удалять старые изображения или нет</b>",
               "enabled_pfp": "<b>Включено вращение изображения профиля</b>",
               "pfp_not_enabled": "<b>Вращение изображения профиля не включено</b>",
               "pfp_disabled": "<b>Поворот изображения профиля отключен</b>",
               "missing_time": "<b>В биографии не указано время</b>",
               "enabled_bio": "<b>Биочасы включены</b>",
               "bio_not_enabled": "<b>Биочасы не включены</b>",
               "disabled_bio": "<b>Биочасы отключены</b>",
               "enabled_name": "<b>Включенные часы имени</b>",
               "name_not_enabled": "<b>Часы имен не включены</b>",
               "disabled_name": "<b>Часы имен отключены</b>",
               "how_many_pfps": "<b>Укажите, сколько изображений профиля следует удалить</b>",
               "invalid_pfp_count": "<b>Недопустимое количество изображений профиля для удаления</b>",
               "removed_pfps": "<b>Удалено {} фото из профиля</b>",
               'pref': '<b>[Qiwi]</b> ',
               'need_arg': '{}need args...',
               'phone_setted_successfully': '{}Номер и токен установлены!',
               'p2p_setted_successfully': '{}Секретный P2P токен установлен!',
               'bal': '{}Баланс: {}',
               'commission': '{}Итоговая сумма: {}\nКомиссия Qiwi: {}\nСумма к зачислению: {}',
               'sent': '{}Средства отправлены!\nID: <code>{}</code>',
               'bill_created': '{}Счёт создан!\n{}\nСтатус счёта: <code>{}</code>',
               'bill_payed': 'Оплачен',
               'bill_notpayed': 'Не оплачен',
               'bill_disabled': 'Автопроверка отключена после 5 минут',
               'bill_link_exp': 'Ссылка истекла по причине оплаты'}
    _db = 'QiwiMod'

    def __init__(self):
        self.bio_enabled = False
        self.name_enabled = False
        self.pfp_enabled = False
        self.raw_bio = None
        self.raw_name = None

    def config_complete(self):
        self.name = self.strings["name"]

    async def client_ready(self, client, db):
        self.client = client
        self.db = db
        self.me = await client.get_me()
        
    def __pad(self, text: bytes):
        return text[:8] if len(text) > 8 else text

    def __get_enc(self, key: str) -> str:
        c = DES.new(self.__pad(hashlib.md5((self.me.phone+str(self.me.id)
                                            ).encode('utf-8')).hexdigest().encode('utf-8')), DES.MODE_ECB)
        return unpad(c.decrypt(self.db.get(self._db, key, b'')), 8).decode('utf-8')

    def __set_enc(self, key: str, value: str):
        c = DES.new(self.__pad(hashlib.md5((self.me.phone+str(self.me.id)
                                            ).encode('utf-8')).hexdigest().encode('utf-8')), DES.MODE_ECB)
        self.db.set(self._db, key, c.encrypt(pad(value.encode('utf-8'), 8)))

    async def qsetp2pcmd(self, m: types.Message):
        '''.qsetp2p <TOKEN>
        Установить секретный p2p ключ'''
        args = utils.get_args(m)
        if args:
            self.__set_enc('p2p', args[0])
            return await utils.answer(m, self.strings('p2p_setted_successfully').format(self.strings('pref')))
        await utils.answer(m, self.strings('need_arg').format(self.strings('pref')))

    async def qsetcmd(self, m: types.Message):
        '''.qset <phone> <TOKEN>
        Установить номер и токен'''
        args = utils.get_args(m)
        if args:
            self.__set_enc('phone', args[0])
            self.__set_enc('token', args[1])
            return await utils.answer(m, self.strings('phone_setted_successfully').format(self.strings('pref')))
        await utils.answer(m, self.strings('need_arg').format(self.strings('pref')))

    async def qbalcmd(self, m: types.Message):
        '.qbal - Получить баланс'
        async with QiwiWrapper(self.__get_enc('token'), self.__get_enc('phone')) as w:
            w: QiwiWrapper
            bal = await w.get_balance()
            await utils.answer(m, self.strings('bal').format(self.strings('pref'), str(bal.amount)+bal.currency.symbol))

    async def qswalcmd(self, m: types.Message):
        '.qswal <phone> <amount> <?comment> - Отправить средства по номеру'
        async with QiwiWrapper(self.__get_enc('token'), self.__get_enc('phone')) as w:
            w: QiwiWrapper
            args = utils.get_args(m)
            args_raw = utils.get_args_raw(m)
            trans_id = await w.to_wallet(
                to_number=args[0],
                amount=int(args[1]),
                comment=args_raw.split(
                    args[1])[1].strip() if len(args) > 2 else None
            )
            await utils.answer(m, self.strings('sent').format(self.strings('pref'), str(trans_id.payment_id)))

    async def qscardcmd(self, m: types.Message):
        '.qscard <card_num[no_spaces]> <amount> - Отправить средства на карту'
        async with QiwiWrapper(self.__get_enc('token'), self.__get_enc('phone')) as w:
            w: QiwiWrapper
            args = utils.get_args(m)
            trans_id = await w.to_card(
                to_card=args[0],
                trans_sum=float(args[1]),
            )
            await utils.answer(m, self.strings('sent').format(self.strings('pref'), str(trans_id.payment_id)))

    async def qcmscmd(self, m: types.Message):
        '.qcms <card_num/phone> <amount> - Посчитать комиссию'
        async with QiwiWrapper(self.__get_enc('token'), self.__get_enc('phone')) as w:
            w: QiwiWrapper
            args = utils.get_args(m)
            commission = await w.calc_commission(args[0], float(args[1]))
            await utils.answer(m, self.strings('commission').format(self.strings('pref'),
                                                                    str(commission.withdraw_sum.amount) +
                                                                    commission.withdraw_sum.currency.symbol,
                                                                    str(commission.qiwi_commission.amount) +
                                                                    commission.qiwi_commission.currency.symbol,
                                                                    str(commission.enrollment_sum.amount) +
                                                                    commission.enrollment_sum.currency.symbol,
                                                                    ))

    async def qp2pcmd(self, m: types.Message):
        '.qp2p <amount> <?comment> - Создать счёт для оплаты'
        async with QiwiWrapper(secret_p2p=self.__get_enc('p2p')) as w:
            w: QiwiWrapper
            args = utils.get_args(m)
            args_raw = utils.get_args_raw(m)
            bill = await w.create_p2p_bill(
                amount=args[0],
                comment=args_raw.split(
                    args[0])[1].strip() if len(args) > 1 else None
            )
            last_status = None
            url = bill.pay_url
            n = 0
            while True:
                if n >= 72:
                    await utils.answer(m, self.strings('bill_created').format(self.strings('pref'), self.strings('bill_link_exp'), self.strings('bill_disabled')))
                    break
                status = await bill.check()
                if status != last_status:
                    last_status = status
                    await utils.answer(m, self.strings('bill_created').format(self.strings('pref'), url,
                                                                              self.strings('bill_payed' if status else 'bill_notpayed')))
                    if status:
                        break
                n += 1
                await asyncio.sleep(5)

    async def autopfpcmd(self, message):
        """Поворачивает изображение вашего профиля каждые 60 секунд на x градусов, использование:
            .autopfp <градусы> <удалить предыдущий (последний pfp)>

            Градусы - 60, -10 и т.д.
            Удалить последний pfp - True/1/False/0, с учетом регистра"""

        if not pil_installed:
            return await utils.answer(message, self.strings["missing_pil"])

        if not await self.client.get_profile_photos("me", limit=1):
            return await utils.answer(message, self.strings["missing_pfp"])

        msg = utils.get_args(message)
        if len(msg) != 2:
            return await utils.answer(message, self.strings["invalid_args"])

        try:
            degrees = int(msg[0])
        except ValueError:
            return await utils.answer(message, self.strings["invalid_degrees"])

        try:
            delete_previous = ast.literal_eval(msg[1])
        except (ValueError, SyntaxError):
            return await utils.answer(message, self.strings["invalid_delete"])

        with BytesIO() as pfp:
            await self.client.download_profile_photo("me", file=pfp)
            raw_pfp = Image.open(pfp)

            self.pfp_enabled = True
            pfp_degree = 0
            await self.allmodules.log("start_autopfp")
            await utils.answer(message, self.strings["enabled_pfp"])

            while self.pfp_enabled:
                pfp_degree = (pfp_degree + degrees) % 360
                rotated = raw_pfp.rotate(pfp_degree)
                with BytesIO() as buf:
                    rotated.save(buf, format="JPEG")
                    buf.seek(0)

                    if delete_previous:
                        await self.client(functions.photos.
                                          DeletePhotosRequest(await self.client.get_profile_photos("me", limit=1)))

                    await self.client(functions.photos.UploadProfilePhotoRequest(await self.client.upload_file(buf)))
                    buf.close()
                await asyncio.sleep(60)

    async def stopautopfpcmd(self, message):
        """Остановить автоповорот авы."""

        if self.pfp_enabled is False:
            return await utils.answer(message, self.strings["pfp_not_enabled"])
        else:
            self.pfp_enabled = False

            await self.client(functions.photos.DeletePhotosRequest(
                await self.client.get_profile_photos("me", limit=1)
            ))
            await self.allmodules.log("stop_autopfp")
            await utils.answer(message, self.strings["pfp_disabled"])

    async def autobiocmd(self, message):
        """Автоматически изменяет биографию вашей учетной записи в соответствии с текущим временем или балансом киви (обновляется раз в 60 секунд):
             .autobio '<текст> optional{time} optional{qiwi}>'"""

        msg = utils.get_args(message)
        if len(msg) != 1:
            return await utils.answer(message, self.strings["invalid_args"])
        raw_bio = msg[0]
        

        self.bio_enabled = True
        self.raw_bio = raw_bio
        await self.allmodules.log("start_autobio")
        await utils.answer(message, self.strings["enabled_bio"])

        while self.bio_enabled is True:
            bio = raw_bio
            if "{time}" in raw_bio:
                current_time = time.strftime("%H:%M")
                if "{qiwi}" in raw_bio:
                    async with QiwiWrapper(self.__get_enc('token'), self.__get_enc('phone')) as w:
                    w: QiwiWrapper
                    fbal = await w.get_balance()
                    bal = int(fbal)
                    bio = raw_bio.format(time=current_time, qiwi=bal)
                else:
                    bio = raw_bio.format(time=current_time)
            else:
                if "{qiwi}" in raw_bio:
                    async with QiwiWrapper(self.__get_enc('token'), self.__get_enc('phone')) as w:
                    w: QiwiWrapper
                    fbal = await w.get_balance()
                    bal = int(fbal)
                    bio = raw_bio.format(qiwi=bal)
            await self.client(functions.account.UpdateProfileRequest(
                about=bio
            ))
            await asyncio.sleep(60)

    async def stopautobiocmd(self, message):
        """Остановить автобио."""

        if self.bio_enabled is False:
            return await utils.answer(message, self.strings["bio_not_enabled"])
        else:
            self.bio_enabled = False
            await self.allmodules.log("stop_autobio")
            await utils.answer(message, self.strings["disabled_bio"])
            if "{time}" in self.raw_bio:
                if "{qiwi}" in self.raw_bio:
                    bio = self.raw_bio.format(time="", qiwi="")
                else:
                    bio = self.raw_bio.format(time="")
            else:
                if "{qiwi}" in self.raw_bio:
                    bio = self.raw_bio.format(qiwi="")
            await self.client(functions.account.UpdateProfileRequest(about=bio))

    async def autonamecmd(self, message):
        """Автоматически изменяет имя вашей учетной записи в соответствии с текущим временем или балансом киви (обновляется раз в 60 секунд):
             .autoname '<текст> optional{time} optional{qiwi}>'"""

        msg = utils.get_args(message)
        if len(msg) != 1:
            return await utils.answer(message, self.strings["invalid_args"])
        raw_name = msg[0]
        if "{time}" not in raw_name:
            return await utils.answer(message, self.strings["missing_time"])

        self.name_enabled = True
        self.raw_name = raw_name
        await self.allmodules.log("start_autoname")
        await utils.answer(message, self.strings["enabled_name"])

        while self.name_enabled is True:
            name = raw_name
            if "{time}" in raw_name:
                current_time = time.strftime("%H:%M")
                if "{qiwi}" in raw_name:
                    async with QiwiWrapper(self.__get_enc('token'), self.__get_enc('phone')) as w:
                    w: QiwiWrapper
                    fbal = await w.get_balance()
                    bal = int(fbal)
                    name = raw_name.format(time=current_time, qiwi=bal)
                else:
                    name = raw_name.format(time=current_time)
            else:
                if "{qiwi}" in raw_name:
                    async with QiwiWrapper(self.__get_enc('token'), self.__get_enc('phone')) as w:
                    w: QiwiWrapper
                    fbal = await w.get_balance()
                    bal = int(fbal)
                    name = raw_name.format(qiwi=bal)
            await self.client(functions.account.UpdateProfileRequest(
                first_name=name
            ))
            await asyncio.sleep(60)

    async def stopautonamecmd(self, message):
        """Остановить автоимя"""

        if self.name_enabled is False:
            return await utils.answer(message, self.strings["name_not_enabled"])
        else:
            self.name_enabled = False
            await self.allmodules.log("stop_autoname")
            await utils.answer(message, self.strings["disabled_name"])
            if "{time}" in self.raw_name:
                if "{qiwi}" in self.raw_name:
                    name = self.raw_name.format(time="", qiwi="")
                else:
                    name = self.raw_name.format(time="")
            else:
                if "{qiwi}" in self.raw_name:
                    name = self.raw_name.format(qiwi="")
            await self.client(functions.account.UpdateProfileRequest(
                first_name=name
            ))

    async def delpfpcmd(self, message):
        """Удалите x фото профиля из своего профиля.
         .delpfp <количество фото/unlimited — удалить все>"""

        args = utils.get_args(message)
        if not args:
            return await utils.answer(message, self.strings["how_many_pfps"])
        if args[0].lower() == "unlimited":
            pfps_count = None
        else:
            try:
                pfps_count = int(args[0])
            except ValueError:
                return await utils.answer(message, self.strings["invalid_pfp_count"])
            if pfps_count <= 0:
                return await utils.answer(message, self.strings["invalid_pfp_count"])

        await self.client(functions.photos.DeletePhotosRequest(await self.client.get_profile_photos("me",
                                                                                                    limit=pfps_count)))

        if pfps_count is None:
            pfps_count = _("all")
        await self.allmodules.log("delpfp")
        await utils.answer(message, self.strings["removed_pfps"].format(str(pfps_count)))
