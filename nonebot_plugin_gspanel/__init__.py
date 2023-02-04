import re
from typing import Tuple

from nonebot import get_driver
from nonebot.adapters import Message
from nonebot.adapters.ntchat import Bot
from nonebot.adapters.ntchat.event import MessageEvent, TextMessageEvent
from nonebot.adapters.ntchat.message import Message, MessageSegment
from nonebot.log import logger
from nonebot.params import CommandArg
from nonebot.plugin import on_command

from ..GenshinUID.GenshinUID.utils.db_operation.db_operation import select_db
from .__utils__ import GSPANEL_ALIAS, aliasWho, fetchInitRes, formatTeam
from .data_source import getPanel, getTeam
from .data_updater import updateCache

driver = get_driver()
driver.on_startup(fetchInitRes)
driver.on_bot_connect(updateCache)

showPanel = on_command("panel", aliases=GSPANEL_ALIAS, priority=13, block=True)
showTeam = on_command("teamdmg", aliases={"队伍伤害"}, priority=13, block=True)

uidStart = ["1", "2", "5", "6", "7", "8", "9"]

# 尽量不改动除了__init__之外的文件
async def formatInput(msg: str, wxid: str) -> Tuple[str, str]:
    """
    输入消息中的 UID 与角色名格式化，应具备处理 ``msg`` 为空、包含中文或数字的能力。
    - 首个中文字符串捕获为角色名，若不包含则返回 ``all`` 请求角色面板列表数据
    - 首个数字字符串捕获为 UID，若不包含则返回 ``uidHelper()`` 根据绑定配置查找的 UID

    * ``param msg: str`` 输入消息，由 ``state["_prefix"]["command_arg"]`` 或 ``event.get_plaintext()`` 生成，可能包含 CQ 码
    * ``param qq: str`` 输入消息触发 QQ
    * ``param atqq: str = ""`` 输入消息中首个 at 的 QQ
    - ``return: Tuple[str, str]``  UID、角色名
    """  # noqa: E501
    uid, char, tmp = "", "", ""
    group = re.findall(
        r"[0-9]+|[\u4e00-\u9fa5]+|[a-z]+", re.sub(r"\[CQ:.*\]", "", msg.split("@")[0]), flags=re.IGNORECASE
    )
    for s in group:
        if s.isdigit():
            if len(s) == 9:
                if not uid:
                    uid = s
            else:
                # 0人，1斗，97忍
                tmp = s
        elif s.encode().isalpha():
            # dio娜，abd
            tmp = s.lower()
        elif not s.isdigit() and not char:
            char = tmp + s
    uid = uid
    char = await aliasWho(char or tmp or "全部")
    return uid, char


@showPanel.handle()
async def giveMePower(event: TextMessageEvent, args: Message = CommandArg()):
    wxid_list = []
    wxid_list.append(event.from_wxid)

    raw_mes = args.extract_plain_text().strip()
    name = ''.join(re.findall('[\u4e00-\u9fa5]', raw_mes))
    if not name:
        return
    if "@" in raw_mes:
        raw_mes = raw_mes.split("@")[0]
        if not raw_mes:
            return

    wxid = event.from_wxid
    if event.at_user_list:
        for user in event.at_user_list:
            user = user.strip()
            if user != "":
                wxid = user

     # 尝试从输入中理解 UID、角色名
    uid, char = await formatInput(raw_mes, wxid)

    if not uid.isdigit() or uid[0] not in uidStart or len(uid) != 9:
        uid = await select_db(wxid, mode='uid')
        if '未找到绑定的UID' in uid:
            await showTeam.finish(MessageSegment.room_at_msg(content=f"要查询角色面板的 UID 捏？"+"{$@}", at_list=wxid_list))
        #await showPanel.finish(MessageSegment.room_at_msg(content=f"UID 是「{uid}」吗？好像不对劲呢.."+"{$@}", at_list=wxid_list))

    logger.info(f"正在查找 UID{uid} 的「{char}」角色面板..")
    rt = await getPanel(uid, char)
    if isinstance(rt, str):
        await showPanel.finish(MessageSegment.text(rt))
    elif isinstance(rt, bytes):
        await showPanel.finish(MessageSegment.image(rt))


@showTeam.handle()
async def x_x(bot: Bot, event: TextMessageEvent, args: Message = CommandArg()):
    wxid_list = []
    wxid_list.append(event.from_wxid)

    raw_mes = args.extract_plain_text().strip()
    name = ''.join(re.findall('[\u4e00-\u9fa5]', raw_mes))
    if "@" in raw_mes:
        raw_mes = raw_mes.split("@")[0]

    wxid = event.from_wxid
    if event.at_user_list:
        for user in event.at_user_list:
            user = user.strip()
            if user != "":
                wxid = user

    # 尝试从输入中理解 UID、角色名
    uid, chars = await formatTeam(raw_mes, wxid)

    if not uid.isdigit() or uid[0] not in uidStart or len(uid) != 9:
        uid = await select_db(wxid, mode='uid')
        if '未找到绑定的UID' in uid:
            await showTeam.finish(MessageSegment.room_at_msg(content=f"要查询角色面板的 UID 捏？"+"{$@}", at_list=wxid_list))

    if not chars:
        logger.info(f"微信 {wxid} ,UID:{uid} 的输入「{raw_mes}」似乎未指定队伍角色！")
    logger.info(f"正在查找 UID{uid} 的「{'/'.join(chars) or '展柜前 4 角色'}」队伍伤害面板..")
    rt = await getTeam(uid, chars)
    if isinstance(rt, str):
        await showTeam.finish(MessageSegment.text(rt))
    elif isinstance(rt, bytes):
        await showTeam.finish(MessageSegment.image(rt))
