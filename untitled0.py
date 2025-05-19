import streamlit as st
import pandas as pd
import numpy as np
import re
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from collections import Counter, defaultdict
import emoji

# --- Style: Make it Cute! ---
st.set_page_config(page_title="💖 Chat Analyzer", layout="centered")
cute_css = """
<style>
/* Main background, cards, and rounded corners */
body { background: #fff4fa !important; }
[data-testid="stAppViewContainer"] { background: linear-gradient(135deg, #fff4fa 70%, #e4e5fb 100%); }
.stButton>button { background: #fc6cb5; color: white; border-radius: 16px; padding: 0.5em 1.2em; font-size: 1.1em;}
.stTabs [role="tab"] { font-size: 1.08em; padding: 8px 22px; border-radius: 16px 16px 0 0; background: #fce0f7; margin-right: 8px; }
.stTabs [aria-selected="true"] { background: #fc6cb5 !important; color: white !important; }
[data-testid="stHeader"] { background: none; }
div[data-testid="stVerticalBlock"] > div { border-radius: 24px; background: #fffafa; box-shadow: 0 4px 16px #fbb6ce44; margin: 16px 0; padding: 16px 20px; }
/* Card style for metric */
.card-metric { background: #fffafa; border-radius: 20px; box-shadow: 0 2px 10px #ffbfd9; padding: 18px 24px; margin-bottom: 16px; display: flex; align-items: center; }
.card-metric .icon { font-size: 2em; margin-right: 14px; }
.stTable { background: #fff4fa !important; border-radius: 12px; }
</style>
"""
st.markdown(cute_css, unsafe_allow_html=True)

st.markdown("<h1 style='text-align:center; color:#fc6cb5;'>💬  Chat Analyzer</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align:center; color:#aa4da2;'>For a playful, insightful look at your WhatsApp chat – optimized for lovebirds and besties!</p>", unsafe_allow_html=True)

# ---- Sidebar for settings ----
st.sidebar.header("🔧 Settings")
end_phrases = st.sidebar.text_area(
    "Conversation End Phrases (comma-separated)", 
    "rüyalar,görüşürüz,iyi geceler,görüşmek üzere",
    height=80
).split(',')
search_phrase = st.sidebar.text_input("Search phrase ( 'özledim', etc.)", value="özledim")
show_emoji_heatmap = st.sidebar.checkbox("Show Emoji Heatmap", value=True)
show_raw_table = st.sidebar.checkbox("Show Raw Table", value=False)

# ---- File Upload or Demo ----
st.write("### 📎 Upload your exported WhatsApp chat (.txt):")
uploaded_file = st.file_uploader(" ", type=["txt"], label_visibility="collapsed")
demo_btn = st.button("Try a Demo Chat 💡")
if demo_btn:
    uploaded_file = "demo_chat.txt"
    if not isinstance(uploaded_file, str):
        with open("demo_chat.txt", "w", encoding="utf-8") as fh:
            fh.write(
                "30.11.2024 13:21 - Mesajlar ve aramalar uçtan uca şifrelidir.\n"
                "3.04.2025 16:34 - Kadir 🐬: Merhaba Sude, ben Kadir. Uzun zaman sonra bir anda yazdığımın farkındayım.\n"
                "3.04.2025 16:48 - Sude Uygun: merhaba kadir\n"
                "3.04.2025 16:48 - Sude Uygun: bu akşam müsait değilim\n"
                "3.04.2025 16:49 - Sude Uygun: yarın kaçta gideceksin\n"
                "3.04.2025 16:50 - Kadir 🐬: Sabah 5.30 - 6 gibi çıkacağım\n"
                "3.04.2025 16:50 - Sude Uygun: anladım\n"
            )

# ---- Regex for New Date Format ----
LINE_RE = re.compile(
    r"^(\d{1,2}\.\d{1,2}\.\d{4})\s+(\d{1,2}:\d{2})\s+-\s([^:]+):\s(.*)$"
)

def parse_chat(file_or_path):
    rows = []
    if isinstance(file_or_path, str):
        lines = open(file_or_path, "r", encoding="utf-8").readlines()
    else:
        lines = file_or_path.read().decode("utf-8").splitlines()
    for line in lines:
        m = LINE_RE.match(line.strip())
        if not m:
            if rows:
                rows[-1]["text"] += " " + line.strip()
            continue
        date_str, time_str, author, text = m.groups()
        try:
            dt = datetime.strptime(f"{date_str} {time_str}", "%d.%m.%Y %H:%M")
        except Exception:
            dt = pd.to_datetime(f"{date_str} {time_str}", dayfirst=True)
        rows.append({
            "dt": dt,
            "author": author.strip(),
            "text": text.strip(),
            "emojis": emoji.distinct_emoji_list(text),
        })
    df = pd.DataFrame(rows)
    return df.sort_values("dt").reset_index(drop=True) if not pd.DataFrame(rows).empty else pd.DataFrame()

def get_conversation_ends(df, end_phrases):
    ends = []
    starters = []
    prev_time = df.iloc[0]["dt"]
    prev_author = df.iloc[0]["author"]
    ends.append(-1)  # so first conversation is from 0
    for i, row in df.iterrows():
        msg = row["text"].lower()
        is_end = any(ep.strip().lower() in msg for ep in end_phrases if ep.strip())
        # End if message matches phrase or time gap
        if is_end or (row["dt"] - prev_time) > timedelta(hours=6):
            ends.append(i)
            if i < len(df) - 1:
                starters.append(df.iloc[i+1]["author"])
        prev_time = row["dt"]
    if not starters and not df.empty:
        starters.append(df.iloc[0]["author"])
    return ends, starters

def classify_response_times(df, split_idx):
    """Label each message as Early (<1m), Near Early (1-5m), or Late (>5m) within its conversation."""
    reply_types = []
    for i, row in df.iterrows():
        # New conversation: no previous message in this segment
        if i in split_idx:
            reply_types.append(None)
            continue
        td = (df.iloc[i]["dt"] - df.iloc[i-1]["dt"])
        if td.total_seconds() < 60:
            reply_types.append("Early (<1m)")
        elif td.total_seconds() < 300:
            reply_types.append("Near Early (1-5m)")
        else:
            reply_types.append("Late (>5m)")
    return reply_types

def favorite_emojis(df):
    all_emojis = []
    for es in df["emojis"]:
        all_emojis.extend(es)
    return Counter(all_emojis).most_common(10)

def phrase_counts(df, phrase):
    phrase = phrase.lower()
    return df[df["text"].str.lower().str.contains(phrase, na=False)].groupby("author").size()

def emoji_timeline(df):
    """Returns DataFrame with date, author, and emoji count per day."""
    if df.empty:
        return pd.DataFrame()
    timeline = df.explode("emojis")
    timeline = timeline.dropna(subset=["emojis"])
    if timeline.empty:
        return pd.DataFrame()
    timeline["date"] = timeline["dt"].dt.date
    return timeline.groupby(["date", "author"])["emojis"].count().reset_index()

def emoji_heatmap_df(df):
    """Returns DataFrame with hour, author, emoji count."""
    timeline = df.explode("emojis").dropna(subset=["emojis"])
    if timeline.empty:
        return pd.DataFrame()
    timeline["hour"] = timeline["dt"].dt.hour
    return timeline.groupby(["hour", "author"])["emojis"].count().reset_index()

# ---- Main App Logic ----
if uploaded_file:
    df = parse_chat(uploaded_file)
    if df.empty:
        st.error("No valid messages found in your file.")
        st.stop()

    end_idxs, conversation_starters = get_conversation_ends(df, end_phrases)
    num_convs = len(end_idxs)
    reply_types = classify_response_times(df, end_idxs)
    df["reply_type"] = reply_types
    df["hour"] = df["dt"].dt.hour
    df["emoji_count"] = df["emojis"].apply(len)

    # --- Tabs ---
    tab_overview, tab_starters, tab_emoji, tab_timing, tab_phrase = st.tabs([
        "Overview", "Conversations", "Emojis", "Timing", "Phrase Counter"
    ])

    # --- Overview Tab ---
    with tab_overview:
        st.markdown("#### ❤️ Relationship Stats")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f"<div class='card-metric'><span class='icon'>📅</span><span><b>{df['dt'].min().date()}</b><br>First Message</span></div>", unsafe_allow_html=True)
        with col2:
            st.markdown(f"<div class='card-metric'><span class='icon'>💬</span><span><b>{len(df):,}</b><br>Total Messages</span></div>", unsafe_allow_html=True)
        with col3:
            st.markdown(f"<div class='card-metric'><span class='icon'>👩‍❤️‍👨</span><span><b>{df['author'].nunique()}</b><br>Participants</span></div>", unsafe_allow_html=True)

        st.markdown("##### Messages by Person")
        st.dataframe(df["author"].value_counts().rename("Messages"), use_container_width=True)

        st.markdown("##### Messages per Day")
        day_counts = df.set_index("dt").resample("D").size().rename("Messages").reset_index()
        fig = px.line(day_counts, x="dt", y="Messages", markers=True, color_discrete_sequence=["#fc6cb5"])
        st.plotly_chart(fig, use_container_width=True)
        if show_raw_table:
            st.dataframe(df, use_container_width=True)

    # --- Conversation Starters Tab ---
    with tab_starters:
        st.markdown("#### 🚦 Conversations and Who Starts")
        st.markdown(f"<div class='card-metric'><span class='icon'>🌟</span><span><b>{num_convs}</b><br>New Conversations</span></div>", unsafe_allow_html=True)
        if conversation_starters:
            starter_counts = pd.Series(conversation_starters).value_counts()
            df_starters = starter_counts.reset_index()
            df_starters.columns = ['Person', 'Count']
            st.markdown("##### Who started new conversations?")
            st.table(df_starters)
            pie = px.pie(
                df_starters,
                names="Person",
                values="Count",
                color_discrete_sequence=["#fc6cb5", "#a1a0fc", "#b3ffcb"],
                title="Conversation Starters"
            )
            st.plotly_chart(pie, use_container_width=True)
        else:
            st.info("No conversation starters detected (check your file or phrase list).")


    # --- Emoji Tab ---
    with tab_emoji:
        st.markdown("#### 😍 Emoji Analysis")
        st.markdown(f"<div class='card-metric'><span class='icon'>😋</span><span><b>{df['emoji_count'].sum()}</b><br>Total Emojis Sent</span></div>", unsafe_allow_html=True)
        st.markdown("##### Top 10 Emojis Used")
        favs = favorite_emojis(df)
        if favs:
            emoji_df = pd.DataFrame(favs, columns=["Emoji", "Count"])
            st.dataframe(emoji_df, use_container_width=True)
        else:
            st.info("No emojis detected!")

        st.markdown("##### Emojis Sent by Each Person")
        emoji_by_author = df.groupby("author")["emoji_count"].sum()
        bar = px.bar(emoji_by_author, orientation='v', color=emoji_by_author.index,
                     color_discrete_sequence=["#fc6cb5", "#a1a0fc", "#b3ffcb"])
        st.plotly_chart(bar, use_container_width=True)

        # Emoji over time
        st.markdown("##### Emoji Timeline (per day)")
        em_timeline = emoji_timeline(df)
        if not em_timeline.empty:
            fig = px.bar(em_timeline, x="date", y="emojis", color="author",
                         labels={"emojis":"Emojis"}, barmode="group",
                         color_discrete_sequence=["#fc6cb5", "#a1a0fc", "#b3ffcb"])
            st.plotly_chart(fig, use_container_width=True)
        if show_emoji_heatmap:
            st.markdown("##### Emoji Heatmap by Hour and Author")
            heat_df = emoji_heatmap_df(df)
            if not heat_df.empty:
                heat_pivot = heat_df.pivot(index="hour", columns="author", values="emojis").fillna(0)
                fig = go.Figure(
                    data=go.Heatmap(
                        z=heat_pivot.values,
                        x=heat_pivot.columns,
                        y=heat_pivot.index,
                        colorscale="RdPu"
                    )
                )
                fig.update_layout(
                    title="Emoji Usage Heatmap (Hour vs. Author)",
                    xaxis_title="Person",
                    yaxis_title="Hour of Day",
                    height=350
                )
                st.plotly_chart(fig, use_container_width=True)

    # --- Timing Tab ---
    with tab_timing:
        st.markdown("#### ⏱️ Timing Analysis")
        timing_df = df[df["reply_type"].notnull()]
        pie_data = timing_df["reply_type"].value_counts()
        st.markdown("##### Message Timing Distribution")
        pie = px.pie(
            pie_data, names=pie_data.index, values=pie_data.values,
            color_discrete_sequence=["#fc6cb5", "#a1a0fc", "#b3ffcb"])
        st.plotly_chart(pie, use_container_width=True)
        st.markdown("##### Distribution per Author")
        pivot = timing_df.pivot_table(index="author", columns="reply_type", values="text", aggfunc="count").fillna(0)
        st.dataframe(pivot, use_container_width=True)

    # --- Phrase Counter Tab ---
    with tab_phrase:
        st.markdown(f"#### 🔎 Who said '{search_phrase}' and how many times?")
        counts = phrase_counts(df, search_phrase)
        if not counts.empty:
            st.table(counts.rename("Count"))
            bar = px.bar(
                counts, labels={"value":f"'{search_phrase}' Count"}, color=counts.index,
                color_discrete_sequence=["#fc6cb5", "#a1a0fc", "#b3ffcb"]
            )
            st.plotly_chart(bar, use_container_width=True)
        else:
            st.info(f"No messages found containing '{search_phrase}'.")

    st.success("🎀")

else:
    st.info("Upload your exported WhatsApp .txt file or try the demo to begin.")

st.markdown("<hr>", unsafe_allow_html=True)
st.markdown("<div style='text-align:center;font-size:1.1em;color:#bb4898;'>Made with ❤️ by Sude Uygun</div>", unsafe_allow_html=True)
