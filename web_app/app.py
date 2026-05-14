import pandas as pd
import streamlit as st
from code_tool import make_repl_tool
from config import API_KEY, BASE_URL, MODEL, SYSTEM_PROMPT
from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_openai import ChatOpenAI

st.set_page_config(page_title="Мини-продукт с LLM-аналитикой", layout="wide")  # noqa: RUF001
st.title("LLM анализ данных")

if "llm" not in st.session_state:
    st.session_state.llm = ChatOpenAI(
        model=MODEL,  # ty:ignore[unknown-argument] # pyrefly: ignore [bad-argument-type]
        temperature=0.0,
        api_key=API_KEY,  # ty:ignore[unknown-argument]
        base_url=BASE_URL,  # ty:ignore[unknown-argument]
    )


if "tool" not in st.session_state:
    st.session_state.tool = make_repl_tool()

if "agent" not in st.session_state:
    st.session_state.agent = create_agent(
        model=st.session_state.llm,
        tools=[st.session_state.tool.tool],  # type: ignore  # noqa: PGH003
        system_prompt=SYSTEM_PROMPT,
        debug=True,
    )

uploaded_file = st.file_uploader("Загрузи CSV или Excel", type=["csv", "xlsx", "xls"])

if uploaded_file:
    file_changed = st.session_state.get("file_name") != uploaded_file.name

    if "df" not in st.session_state or file_changed:
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)

        st.session_state.df = df
        st.session_state.file_name = uploaded_file.name

        st.session_state.tool.df = df

        if file_changed:
            st.session_state.messages = []

    st.success(
        f"✅ {st.session_state.file_name} — "
        f"{len(st.session_state.df)} строк, {len(st.session_state.df.columns)} столбцов"
    )
    st.dataframe(st.session_state.df.head())

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            for img_bytes in msg.get("images", []):
                st.image(img_bytes)

    if prompt := st.chat_input("Что анализируем?"):
        st.session_state.messages.append(
            {"role": "user", "content": prompt, "images": []}
        )
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            thinking = st.empty()
            thinking.markdown("Агент думает...")

            user_prompt = (
                f"Файл: {st.session_state.file_name}\n"
                # f"Информация о датасете: {st.session_state.df.info()}"  # FIXME: почему-то выдает None  # noqa: RUF003
                f"Задача: {prompt}\n"
                f"Данные уже в переменной df."
            )

            st.session_state.tool.reset_for_new_query()

            full_response = ""
            captured_images: list[bytes] = []

            try:
                result = st.session_state.agent.invoke(
                    {"messages": [HumanMessage(content=user_prompt)]},
                    config={"recursion_limit": 15},
                )

                messages = result.get("messages", [])

                for m in reversed(messages):
                    if isinstance(m, AIMessage) and m.content and m.content.strip():
                        full_response = m.content
                        break

                if not full_response:
                    tool_results = [
                        m.content
                        for m in messages
                        if isinstance(m, ToolMessage) and m.content
                    ]

                    if tool_results:
                        full_response = (
                            "**Результаты анализа:**\n\n"
                            + "\n\n---\n\n".join(tool_results)
                        )

                thinking.empty()

                if full_response:
                    st.markdown(full_response)

                captured_images: list[bytes] = list(st.session_state.tool.all_images)

                for img_bytes in captured_images:
                    st.image(img_bytes)

                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": full_response,
                        "images": captured_images,
                    }
                )

            except Exception:  # noqa: BLE001
                thinking.empty()
                st.error("Ошибка агента, попробуйте еще раз")

else:
    st.info("Загрузи CSV или Excel файл, чтобы начать анализ")
