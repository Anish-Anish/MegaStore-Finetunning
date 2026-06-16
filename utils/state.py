DEFAULTS = {
    "persona":                "business",
    "user_id":                None,
    "user_name":              None,
    "user_role":              None,
    "avatar_initial":         "P",
    "avatar_color":           "#7C3AED",
    "token":                  None,
    "active_request_id":      None,           # None = chat landing (textbox + suggestions only)
    "history":                [],
    "active_pipelines_count": 3,
    "engineer_tab":           "review",
    "prefill_question":       "",
    "logged_in":              False,
    "_last_q":                "",            # query-param change detection
    "_last_open":             None,
    "_pending_ask":           None,          # a suggestion chip asked → submit on next run
    "editing_card":           None,          # request_id of the review card being edited
    "show_panel":             True,          # custom left drawer open/closed
}


def init_state():
    import streamlit as st
    for k, v in DEFAULTS.items():
        if k not in st.session_state:
            st.session_state[k] = v
