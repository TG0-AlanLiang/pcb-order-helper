"""PCB-specific bilingual translator with terminology dictionary."""
from __future__ import annotations

import re

# PCB / Electronics manufacturing terminology dictionary
# English -> Chinese
EN_TO_CN = {
    # PCB types & structure
    "rigid": "硬板",
    "flexible": "柔性板",
    "flex": "柔性",
    "fpc": "FPC柔性板",
    "rigid-flex": "刚柔结合板",
    "single-sided": "单面板",
    "double-sided": "双面板",
    "multilayer": "多层板",
    "layer": "层",
    "inner layer": "内层",
    "outer layer": "外层",
    "core": "芯板",
    "prepreg": "半固化片",
    "stackup": "叠层结构",
    "stack-up": "叠层结构",

    # Stiffener & reinforcement
    "stiffener": "补强",
    "pi stiffener": "PI补强",
    "polyimide stiffener": "PI补强",
    "steel stiffener": "钢片补强",
    "stainless steel stiffener": "不锈钢补强",
    "fr4 stiffener": "FR4补强",
    "adhesive tape": "粘性胶带",
    "3m tape": "3M胶带",
    "reinforcement": "补强",
    "backing": "背胶",

    # Surface finish
    "hasl": "喷锡",
    "lead-free hasl": "无铅喷锡",
    "enig": "沉金",
    "osp": "OSP",
    "immersion gold": "沉金",
    "immersion silver": "沉银",
    "immersion tin": "沉锡",
    "hard gold": "硬金",
    "gold finger": "金手指",

    # Solder mask & silkscreen
    "solder mask": "阻焊层",
    "soldermask": "阻焊层",
    "coverlay": "覆盖膜",
    "silkscreen": "丝印",
    "legend": "丝印",

    # Drilling & vias
    "via": "过孔",
    "through-hole": "通孔",
    "blind via": "盲孔",
    "buried via": "埋孔",
    "via-in-pad": "盘中孔",
    "micovia": "微孔",
    "pth": "镀通孔",
    "npth": "非镀通孔",
    "slot": "槽孔",
    "drill": "钻孔",

    # Impedance & electrical
    "impedance control": "阻抗控制",
    "controlled impedance": "控制阻抗",
    "impedance": "阻抗",
    "characteristic impedance": "特性阻抗",
    "differential pair": "差分对",
    "single-ended": "单端",

    # EMI & shielding
    "emi shield": "EMI屏蔽",
    "emi shielding": "EMI屏蔽",
    "shielding": "屏蔽",
    "ground plane": "接地层",

    # Manufacturing
    "panelization": "拼板",
    "panel": "拼板",
    "v-cut": "V割",
    "v-score": "V割",
    "tab routing": "邮票孔",
    "mouse bite": "邮票孔",
    "breakaway tab": "连接条",
    "fiducial": "基准点",
    "tooling hole": "工装孔",
    "outline": "外形",
    "profile": "外形",
    "board outline": "板框",
    "edge plating": "侧面镀铜",
    "castellated holes": "半孔",
    "half-hole": "半孔",
    "chamfer": "倒角",
    "bevel": "斜边",
    "countersink": "沉头孔",
    "counterbore": "沉孔",
    "copper weight": "铜厚",
    "copper thickness": "铜厚",

    # SMT / Assembly
    "smt": "贴片",
    "assembly": "贴片/组装",
    "pick and place": "贴片坐标",
    "bom": "物料清单",
    "bill of materials": "物料清单",
    "reflow": "回流焊",
    "wave soldering": "波峰焊",
    "hand soldering": "手工焊接",
    "stencil": "钢网",
    "solder paste": "锡膏",
    "component": "元器件",
    "capacitor": "电容",
    "resistor": "电阻",
    "inductor": "电感",
    "connector": "连接器",
    "diode": "二极管",
    "transistor": "晶体管",
    "ic": "集成电路",
    "led": "发光二极管",
    "crystal": "晶振",
    "oscillator": "振荡器",
    "buzzer": "蜂鸣器",
    "relay": "继电器",
    "fuse": "保险丝",
    "switch": "开关",
    "button": "按键",
    "header": "排针",
    "socket": "插座",
    "terminal": "端子",

    # Testing
    "flying probe": "飞针测试",
    "e-test": "电测",
    "electrical test": "电气测试",
    "aoi": "AOI光学检测",
    "x-ray": "X光检测",
    "ict": "ICT测试",

    # Materials
    "fr4": "FR4",
    "polyimide": "聚酰亚胺",
    "pi": "PI(聚酰亚胺)",
    "rogers": "罗杰斯",
    "aluminum": "铝基板",
    "copper clad": "覆铜板",

    # Shipping & logistics
    "eta": "预计到达时间",
    "etd": "预计发货时间",
    "tracking number": "运单号",
    "waybill": "运单",
    "express delivery": "快递",
    "shipment": "发货",

    # Quality
    "ipc class 2": "IPC二级",
    "ipc class 3": "IPC三级",
    "ul certification": "UL认证",
    "rohs": "RoHS",

    # EQ related
    "engineering question": "工程问题",
    "eq": "工程问题(EQ)",
    "design rule": "设计规则",
    "clearance": "间距",
    "annular ring": "焊环",
    "minimum trace width": "最小线宽",
    "minimum spacing": "最小间距",
    "gerber": "Gerber文件",
    "drill file": "钻孔文件",
}

# Build reverse dictionary (Chinese -> English)
CN_TO_EN = {v.lower(): k for k, v in EN_TO_CN.items()}


def detect_language(text: str) -> str:
    """Detect if text is primarily Chinese or English."""
    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    total_alpha = len(re.findall(r"[a-zA-Z]", text))
    if chinese_chars > total_alpha:
        return "zh"
    return "en"


def translate_with_dict(text: str, direction: str = "auto") -> tuple[str, str, list[tuple[str, str]]]:
    """Translate text using PCB terminology dictionary.

    Args:
        text: Input text to translate
        direction: "en2cn", "cn2en", or "auto"

    Returns:
        (translated_text, direction_used, matched_terms)
    """
    if direction == "auto":
        direction = "en2cn" if detect_language(text) == "en" else "cn2en"

    dictionary = EN_TO_CN if direction == "en2cn" else CN_TO_EN
    matched_terms = []
    result = text

    # Sort by length (longest first) to avoid partial matches
    sorted_terms = sorted(dictionary.keys(), key=len, reverse=True)

    for term in sorted_terms:
        translation = dictionary[term]
        # Use word boundaries for short terms to avoid false matches
        # e.g., "eq" should not match inside "required"
        escaped = re.escape(term)
        if len(term) <= 3:
            pattern = re.compile(r"\b" + escaped + r"\b", re.IGNORECASE)
        else:
            pattern = re.compile(escaped, re.IGNORECASE)
        if pattern.search(result):
            matched_terms.append((term, translation))
            result = pattern.sub(f"【{translation}】", result)

    return result, direction, matched_terms


def get_process_notes_template() -> str:
    """Return a template for common FPC/PCB process notes in Chinese."""
    return """常用工艺备注模板：

【补强要求】
- 背面PI补强，厚度0.2mm，3M胶粘贴
- 正面EMI屏蔽膜补强
- 不锈钢补强片，厚度0.3mm

【特殊工艺】
- 阻抗控制，请按叠层结构要求生产
- 盘中孔工艺
- 半孔工艺
- 侧面镀铜

【拼板要求】
- V割拼板
- 邮票孔连接

【表面处理】
- 沉金 (ENIG)
- 无铅喷锡 (Lead-free HASL)
- OSP
"""
