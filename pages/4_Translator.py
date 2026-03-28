"""PCB Translator - Bilingual translation tool for PCB terminology."""
import streamlit as st

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.translator import translate_with_dict, detect_language, get_process_notes_template, EN_TO_CN

st.title("🌐 PCB Translator")

tab1, tab2, tab3 = st.tabs([
    "General Translate",
    "Process Notes (EN→CN)",
    "Terminology Dictionary",
])

# === Tab 1: General Translation ===
with tab1:
    st.header("General PCB Translation")
    st.markdown("Paste any PCB-related text. Language direction is auto-detected, or you can override.")

    direction = st.radio(
        "Direction",
        ["Auto-detect", "English → Chinese", "Chinese → English"],
        horizontal=True,
    )
    dir_map = {
        "Auto-detect": "auto",
        "English → Chinese": "en2cn",
        "Chinese → English": "cn2en",
    }

    input_text = st.text_area(
        "Input text:",
        height=200,
        placeholder="Paste Slack message, JLC EQ reply, or any PCB-related text here...",
    )

    if input_text:
        translated, direction_used, matched = translate_with_dict(input_text, dir_map[direction])

        detected_lang = "English → Chinese" if direction_used == "en2cn" else "Chinese → English"
        st.markdown(f"**Detected direction:** {detected_lang}")

        st.subheader("Translation Result")
        st.text_area("Output (copy this):", value=translated, height=200, key="output")

        if matched:
            with st.expander(f"Matched Terms ({len(matched)})"):
                for orig, trans in matched:
                    st.markdown(f"- **{orig}** → {trans}")

# === Tab 2: Process Notes ===
with tab2:
    st.header("Process Notes Translation (EN → CN)")
    st.markdown("Translate engineering notes for JLC order remarks. Input English, get Chinese output.")

    notes_input = st.text_area(
        "English process notes:",
        height=200,
        placeholder="e.g., PI stiffener on back side, 0.2mm thickness, adhesive tape attachment\nEMI shielding on top side\nImpedance control required",
    )

    if notes_input:
        translated, _, matched = translate_with_dict(notes_input, "en2cn")
        st.subheader("Chinese Output (paste to JLC remarks)")
        st.text_area("Chinese notes:", value=translated, height=200, key="cn_output")

        if matched:
            with st.expander(f"Matched Terms ({len(matched)})"):
                for orig, trans in matched:
                    st.markdown(f"- **{orig}** → {trans}")

    st.markdown("---")
    with st.expander("Common Process Notes Templates"):
        st.markdown(get_process_notes_template())

# === Tab 3: Dictionary ===
with tab3:
    st.header("PCB Terminology Dictionary")
    st.markdown(f"**{len(EN_TO_CN)} terms** in the dictionary.")

    search = st.text_input("Search term (English or Chinese):")

    # Group by category
    categories = {
        "PCB Types & Structure": ["rigid", "flexible", "flex", "fpc", "rigid-flex", "single-sided", "double-sided", "multilayer", "layer", "inner layer", "outer layer", "core", "prepreg", "stackup", "stack-up"],
        "Stiffener & Reinforcement": ["stiffener", "pi stiffener", "polyimide stiffener", "steel stiffener", "stainless steel stiffener", "fr4 stiffener", "adhesive tape", "3m tape", "reinforcement", "backing"],
        "Surface Finish": ["hasl", "lead-free hasl", "enig", "osp", "immersion gold", "immersion silver", "immersion tin", "hard gold", "gold finger"],
        "Solder Mask & Silkscreen": ["solder mask", "soldermask", "coverlay", "silkscreen", "legend"],
        "Drilling & Vias": ["via", "through-hole", "blind via", "buried via", "via-in-pad", "micovia", "pth", "npth", "slot", "drill"],
        "Impedance & Electrical": ["impedance control", "controlled impedance", "impedance", "characteristic impedance", "differential pair", "single-ended"],
        "EMI & Shielding": ["emi shield", "emi shielding", "shielding", "ground plane"],
        "Manufacturing": ["panelization", "panel", "v-cut", "v-score", "tab routing", "mouse bite", "breakaway tab", "fiducial", "tooling hole", "outline", "profile", "board outline", "edge plating", "castellated holes", "half-hole", "chamfer", "bevel", "countersink", "counterbore", "copper weight", "copper thickness"],
        "SMT / Assembly": ["smt", "assembly", "pick and place", "bom", "bill of materials", "reflow", "wave soldering", "hand soldering", "stencil", "solder paste"],
        "Components": ["component", "capacitor", "resistor", "inductor", "connector", "diode", "transistor", "ic", "led", "crystal", "oscillator", "buzzer", "relay", "fuse", "switch", "button", "header", "socket", "terminal"],
        "Testing": ["flying probe", "e-test", "electrical test", "aoi", "x-ray", "ict"],
        "Materials": ["fr4", "polyimide", "pi", "rogers", "aluminum", "copper clad"],
        "Shipping & Logistics": ["eta", "etd", "tracking number", "waybill", "express delivery", "shipment"],
        "EQ Related": ["engineering question", "eq", "design rule", "clearance", "annular ring", "minimum trace width", "minimum spacing", "gerber", "drill file"],
    }

    for cat_name, terms in categories.items():
        filtered_terms = []
        for term in terms:
            cn = EN_TO_CN.get(term, "")
            if search:
                if search.lower() in term.lower() or search in cn:
                    filtered_terms.append((term, cn))
            else:
                filtered_terms.append((term, cn))

        if filtered_terms:
            with st.expander(f"{cat_name} ({len(filtered_terms)} terms)"):
                for en, cn in filtered_terms:
                    st.markdown(f"- **{en}** → {cn}")
