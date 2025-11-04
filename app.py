import streamlit as st
import pandas as pd

# ------------------------------
# Page Config
# -------------------------------
st.set_page_config(layout="wide")

# -------------------------------
# CONFIG
# -------------------------------
THEME_WEIGHTS = {
    "household_kids": 9,
    "special_cases": 8,
    "pets": 8,
    "living": 9,
    "nationality": 8,
    "cuisine": 6
}

BONUS_CAP = 10  # max total bonus %

# -------------------------------
# HELPER FUNCTIONS WITH EXPLANATIONS
# -------------------------------

def score_household_kids(client, maid, exp):
    w = THEME_WEIGHTS["household_kids"]

    # Case 1: Client unspecified → Neutral
    if client == "unspecified":
        return None, "Neutral: client did not specify household type"

    # Define experience set for readability
    has_exp = exp in ["lessthan2", "above2", "both"]

    # Case 2: Client = baby
    if client == "baby":
        if maid in ["refuses_baby", "refuses_baby_and_kids"]:
            if has_exp:
                return 8, "Partial: maid has childcare experience despite refusal (baby)"
            return 0, "Mismatch: maid refuses baby care"
        elif has_exp:
            return 10, "Perfect match: maid accepts and has childcare experience (baby)"
        else:
            return 9, "Standard match: maid accepts baby care without experience"

    # Case 3: Client = many kids
    if client == "many_kids":
        if maid in ["refuses_many_kids", "refuses_baby_and_kids"]:
            if has_exp:
                return 8, "Partial: maid has childcare experience despite refusal (many kids)"
            return 0, "Mismatch: maid refuses many kids"
        elif has_exp:
            return 10, "Perfect match: maid accepts and has childcare experience (many kids)"
        else:
            return 9, "Standard match: maid accepts many kids without experience"

    # Case 4: Client = baby and kids
    if client == "baby_and_kids":
        if maid in ["refuses_baby_and_kids", "refuses_baby", "refuses_many_kids"]:
            if has_exp:
                return 8, "Partial: maid has childcare experience despite refusal (baby_and_kids)"
            return 0, "Mismatch: maid refuses baby_and_kids"
        elif has_exp:
            return 10, "Perfect match: maid accepts and has childcare experience (baby_and_kids)"
        else:
            return 9, "Standard match: maid accepts baby_and_kids without experience"

    # Case 5: Experience only (no clear acceptance or refusal)
    if has_exp:
        return 8, "Partial: maid has childcare experience only (no stated preference)"

    # Case 6: Default
    return None, "Neutral"


def score_special_cases(client, maid):
    w = THEME_WEIGHTS["special_cases"]
    if client == "unspecified":
        return None, "Neutral: client did not specify special cases"
    if client == "elderly":
        if maid in ["elderly_experienced", "elderly_and_special"]:
            return w, "Match: elderly supported"
        elif maid == "special_needs":
            return int(w * 0.6), "Partial: client elderly, maid only has special_needs"
    if client == "special_needs":
        if maid in ["special_needs", "elderly_and_special"]:
            return w, "Match: special needs supported"
        elif maid == "elderly_experienced":
            return int(w * 0.6), "Partial: client special_needs, maid only elderly"
    if client == "elderly_and_special":
        if maid == "elderly_and_special":
            return w, "Perfect match: elderly + special needs"
        elif maid in ["elderly_experienced", "special_needs"]:
            return int(w * 0.6), "Partial: maid covers only one"
    return None, "Neutral"

def score_pets(client, maid, handling):
    w = THEME_WEIGHTS["pets"]
    if client == "unspecified":
        return None, "Neutral: client did not specify pets"
    if client == "cat":
        if maid in ["refuses_cat", "refuses_both_pets"]:
            if handling in ["cats", "both"]:
                return int(w * 1.2), "Bonus: maid reports cat handling despite refusal"
            return 0, "Mismatch: maid refuses cats"
        elif handling in ["cats", "both"]:
            return int(w * 1.2), "Bonus: maid has cat handling experience"
        else:
            return w, "Match: cats allowed"
    if client == "dog":
        if maid in ["refuses_dog", "refuses_both_pets"]:
            if handling in ["dogs", "both"]:
                return int(w * 1.2), "Bonus: maid reports dog handling despite refusal"
            return 0, "Mismatch: maid refuses dogs"
        elif handling in ["dogs", "both"]:
            return int(w * 1.2), "Bonus: maid has dog handling experience"
        else:
            return w, "Match: dogs allowed"
    if client == "both":
        if maid in ["refuses_both_pets", "refuses_cat", "refuses_dog"]:
            if handling in ["cats", "dogs", "both"]:
                return int(w * 1.2), "Bonus: maid reports pet handling despite refusal"
            return 0, "Mismatch: maid refuses one or both pets"
        elif handling == "both":
            return int(w * 1.2), "Bonus: maid prefers handling both cats & dogs"
        else:
            return w, "Match: both cats & dogs allowed"
    return None, "Neutral"

def score_living(client, maid):
    w = THEME_WEIGHTS["living"]

    # Case 1: Both sides unspecified or unrestricted → Match
    if client == "unspecified" and maid == "no_restriction_living_arrangement":
        return w, "Match: both sides unrestricted, flexible and compatible"

    # Case 2: Client unspecified → Neutral
    if client == "unspecified":
        return None, "Neutral: client did not specify living arrangement"

    # Case 3: Maid requires private room but client doesn't provide one → Mismatch
    if "requires_private_room" in maid and "private_room" not in client:
        return 0, "Mismatch: maid requires private room but client did not offer one"

    # Case 4: Maid refuses Abu Dhabi but client does not mention Abu Dhabi → Match (irrelevant refusal)
    if "refuses_abu_dhabi" in maid and "abu_dhabi" not in client:
        return w, "Match: maid refuses Abu Dhabi and client not in Abu Dhabi"

    # Case 5: Client and maid both require private room → Perfect match
    if client in ["private_room", "live_out+private_room"] and "requires_private_room" in maid:
        return w, "Match: both client and maid require private room"
    
    # Case 6: Client requires private room (maid doesn’t specifically require it) → Standard match
    if client in ["private_room", "live_out+private_room"]:
        return w, "Match: private room requirement satisfied"

    # Case 7: Client requires Abu Dhabi posting → check maid’s refusal
    if client in ["private_room+abu_dhabi", "live_out+private_room+abu_dhabi"]:
        if "refuses_abu_dhabi" in maid:
            return 0, "Mismatch: maid refuses Abu Dhabi"
        else:
            return w, "Match: Abu Dhabi posting acceptable"

    # Case 8: Default → Neutral
    return None, "Neutral"


def score_nationality(client, maid):
    w = THEME_WEIGHTS["nationality"]
    if client == "any":
        return w, f"Match: client accepts any nationality, maid is {maid}"
    mapping = {
        "filipina": "filipina",
        "ethiopian maid": "ethiopian",
        "west african nationality": "west_african"
    }
    prefs = client.split("+")
    prefs = [mapping.get(p.strip(), p.strip()) for p in prefs]
    if maid in prefs:
        return w, f"Match: client prefers {client}, maid is {maid}"
    if maid == "indian":
        return 0, "Mismatch: client does not accept indian nationality"
    return 0, f"Mismatch: client prefers {client}, maid is {maid}"

def score_cuisine(client, maid_flags):
    w = THEME_WEIGHTS["cuisine"]
    if client == "unspecified":
        return None, "Neutral: client did not specify cuisine"
    prefs = client.split("+")
    prefs = [p.strip() for p in prefs]
    matches = 0
    if "lebanese" in prefs and maid_flags.get("maid_cooking_lebanese", 0) == 1:
        matches += 1
    if "khaleeji" in prefs and maid_flags.get("maid_cooking_khaleeji", 0) == 1:
        matches += 1
    if "international" in prefs and maid_flags.get("maid_cooking_international", 0) == 1:
        matches += 1
    if matches == 0:
        return 0, "Mismatch: no requested cuisines matched"
    if matches == len(prefs):
        return w, "Perfect match: all cuisines covered"
    if len(prefs) == 2 and matches == 1:
        return int(w * 0.6), "Partial match: 1 of 2 cuisines covered"
    if len(prefs) == 3:
        if matches == 2:
            return int(w * 0.8), "Partial match: 2 of 3 cuisines covered"
        if matches == 1:
            return int(w * 0.5), "Weak partial match: 1 of 3 cuisines covered"
    return int(w * (matches / len(prefs))), f"Partial match: {matches} of {len(prefs)} cuisines covered"

def score_bonuses(row):
    bonuses, explanations = 0, []

    # --- Language bonus ---
    num_langs = row.get("num_languages", 0)
    if num_langs > 2:
        bonuses += 2
        explanations.append(f"Bonus: speaks {num_langs} languages")

    # --- Travel & relocation preference ---
    travel = str(row.get("maidpref_travel", "unspecified")).lower()
    if travel in ["travel", "relocate", "travel_and_relocate"]:
        bonuses += 2
        explanations.append("Bonus: open to travel/relocation")

    # --- Smoking preference ---
    smoking = str(row.get("maidpref_smoking", "unspecified")).lower()
    if smoking == "non_smoker":
        bonuses += 1
        explanations.append("Bonus: non-smoker")

    # --- Education level ---
    edu = str(row.get("maidpref_education", "unspecified")).lower()
    if edu == "school":
        bonuses += 1
        explanations.append("Bonus: educated (school level)")
    elif edu == "university":
        bonuses += 1
        explanations.append("Bonus: university-educated")
    elif edu == "both":
        bonuses += 2
        explanations.append("Bonus: school + university educated")

    # --- Personality traits ---
    pers = str(row.get("maidpref_personality", "")).lower()
    if "energetic" in pers:
        bonuses += 1
        explanations.append("Bonus: energetic personality")
    if "no_attitude" in pers:
        bonuses += 1
        explanations.append("Bonus: respectful / no attitude")
    if "no_tiktok" in pers:
        bonuses += 1
        explanations.append("Bonus: disciplined / no TikTok use")
    if "veg_friendly" in pers:
        bonuses += 1
        explanations.append("Bonus: vegetarian-friendly")

    # --- Experience ---
    exp = row.get("years_of_experience", 0)
    if exp > 5:
        bonuses += 2
        explanations.append(f"Bonus: {exp} years of experience")

    # Cap total bonus
    final_bonus = min(bonuses, BONUS_CAP)

    return final_bonus, explanations


def calculate_score(row):
    theme_scores = {}
    scores, max_weights = [], []
    s, r = score_household_kids(row["clientmts_household_type"], row["maidmts_household_type"], row["maidpref_kids_experience"])
    theme_scores["Household & Kids Reason"] = r
    if s is not None: scores.append(s); max_weights.append(THEME_WEIGHTS["household_kids"])
    s, r = score_special_cases(row["clientmts_special_cases"], row["maidpref_caregiving_profile"])
    theme_scores["Special Cases Reason"] = r
    if s is not None: scores.append(s); max_weights.append(THEME_WEIGHTS["special_cases"])
    s, r = score_pets(row["clientmts_pet_type"], row["maidmts_pet_type"], row["maidpref_pet_handling"])
    theme_scores["Pets Reason"] = r
    if s is not None: scores.append(s); max_weights.append(THEME_WEIGHTS["pets"])
    s, r = score_living(row["clientmts_living_arrangement"], row["maidmts_living_arrangement"])
    theme_scores["Living Reason"] = r
    if s is not None: scores.append(s); max_weights.append(THEME_WEIGHTS["living"])
    s, r = score_nationality(row["clientmts_nationality_preference"], row["maid_grouped_nationality"])
    theme_scores["Nationality Reason"] = r
    if s is not None: scores.append(s); max_weights.append(THEME_WEIGHTS["nationality"])
    maid_flags = {
        "maid_cooking_lebanese": row["maid_cooking_lebanese"],
        "maid_cooking_khaleeji": row["maid_cooking_khaleeji"],
        "maid_cooking_international": row["maid_cooking_international"]
    }
    s, r = score_cuisine(row["clientmts_cuisine_preference"], maid_flags)
    theme_scores["Cuisine Reason"] = r
    if s is not None: scores.append(s); max_weights.append(THEME_WEIGHTS["cuisine"])
    if not scores:
        return 0, "Neutral", theme_scores, []
    base_score = sum(scores) / sum(max_weights) * 100
    bonus, bonus_reasons = score_bonuses(row)
    final_score = min(base_score + bonus, 100)
    return round(final_score, 1), theme_scores, bonus_reasons

# -------------------------------
# STREAMLIT APP
# -------------------------------
st.title("Client–Maid Matching Score Calculator")

uploaded_file = st.file_uploader("Upload your dataset (CSV or Excel)", type=["csv", "xlsx"])
if uploaded_file:
    df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith(".csv") else pd.read_excel(uploaded_file)

    # Create tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Matching Scores", "Optimal Matches","Customer Interface", "Maid Profile Explorer", "Summary Metrics"])

    # ---------------- Tab 1: Existing Matching ----------------
    with tab1:
        st.write("### Matching Scores (Key Fields Only)")
        results = []
        for _, row in df.iterrows():
            score, reasons, bonus_reasons = calculate_score(row)
            result_row = {
                "client_name": row["client_name"],
                "maid_id": row["maid_id"],
                "Final Score %": score,
                **reasons,
                "Bonus Reasons": ", ".join(bonus_reasons) if bonus_reasons else "None"
            }
            results.append(result_row)
        results_df = pd.DataFrame(results)
        st.dataframe(results_df)

        st.write("### Detailed Explanations")
        pair_options = results_df.apply(lambda r: f"{r['client_name']} ↔ {r['maid_id']} ({r['Final Score %']}%)", axis=1)
        selected_pair = st.selectbox("Select a Client–Maid Pair", pair_options)

        if selected_pair:
            row = results_df.iloc[pair_options.tolist().index(selected_pair)]
            st.subheader(f"Explanation for {row['client_name']} ↔ {row['maid_id']}")
            st.write("**Household & Kids:**", row["Household & Kids Reason"])
            st.write("**Special Cases:**", row["Special Cases Reason"])
            st.write("**Pets:**", row["Pets Reason"])
            st.write("**Living:**", row["Living Reason"])
            st.write("**Nationality:**", row["Nationality Reason"])
            st.write("**Cuisine:**", row["Cuisine Reason"])
            st.write("**Bonus:**", row["Bonus Reasons"])

        # Save Tab 1 results in memory for later tabs
        st.session_state["results_df"] = results_df
        
        # Existing download button
        st.download_button(
            "Download Results CSV",
            results_df.to_csv(index=False).encode("utf-8"),
            "matching_results.csv",
            "text/csv"
        )    

    # ---------------- Tab 2: Optimal Matches ----------------
    # ---------------- Preprocessing Step ----------------
    # Keep only relevant columns
    with tab2:
        client_cols = [
            "client_name", "clientmts_household_type", "clientmts_special_cases",
            "clientmts_pet_type", "clientmts_dayoff_policy",
            "clientmts_nationality_preference", "clientmts_living_arrangement",
            "clientmts_cuisine_preference"
        ]
        
        maid_cols = [
            "maid_id", "years_of_experience", "maidspeaks_amharic", "maidspeaks_arabic",
            "maidspeaks_english", "maidspeaks_french", "maidspeaks_oromo",
            "maid_grouped_nationality", "maid_cooking_khaleeji", "maid_cooking_lebanese",
            "maid_cooking_international", "maid_cooking_not_specified",
            "maidmts_household_type", "maidmts_pet_type", "maidmts_dayoff_policy",
            "maidmts_living_arrangement", "maidpref_education", "maidpref_kids_experience",
            "maidpref_pet_handling", "maidpref_personality", "maidpref_travel",
            "maidpref_smoking", "maidpref_caregiving_profile"
        ]
        
        # Split into clients and maids
        clients_df = df[client_cols].drop_duplicates(subset=["client_name"]).reset_index(drop=True)
        maids_df = df[maid_cols].drop_duplicates(subset=["maid_id"]).reset_index(drop=True)
        
        st.write(f" Deduplication complete: {len(clients_df)} unique clients, {len(maids_df)} unique maids.")
    
        # Preview clients_df
        st.write("### Clients (deduplicated)")
        st.dataframe(clients_df.head(20))   # show first 20 rows
        st.write("Client columns:", clients_df.columns.tolist())
        
        # Preview maids_df
        st.write("### Maids (deduplicated)")
        st.dataframe(maids_df.head(20))   # show first 20 rows
        st.write("Maid columns:", maids_df.columns.tolist())

        st.write("### Optimal Matches (Top 2 Maids per Client)")
    
        @st.cache_data
        def compute_optimal_matches(clients_df, maids_df):
            results = []
            for _, client_row in clients_df.iterrows():
                candidate_scores = []
                for _, maid_row in maids_df.iterrows():
                    combined_row = {**client_row.to_dict(), **maid_row.to_dict()}
                    score, reasons, bonus_reasons = calculate_score(combined_row)
                    candidate_scores.append({
                        "maid_id": maid_row["maid_id"],
                        "Final Score %": score,
                        **reasons,
                        "Bonus Reasons": ", ".join(bonus_reasons) if bonus_reasons else "None"
                    })
                # pick top 2
                top_matches = sorted(candidate_scores, key=lambda x: x["Final Score %"], reverse=True)[:2]
                for match in top_matches:
                    results.append({
                        "client_name": client_row["client_name"],
                        "maid_id": match["maid_id"],
                        "Final Score %": match["Final Score %"],
                        "Household & Kids Reason": match["Household & Kids Reason"],
                        "Special Cases Reason": match["Special Cases Reason"],
                        "Pets Reason": match["Pets Reason"],
                        "Living Reason": match["Living Reason"],
                        "Nationality Reason": match["Nationality Reason"],
                        "Cuisine Reason": match["Cuisine Reason"],
                        "Bonus Reasons": match["Bonus Reasons"]
                    })
            return pd.DataFrame(results)
    
        # Run cached optimal matches
        optimal_df = compute_optimal_matches(clients_df, maids_df)
        st.dataframe(optimal_df)
    
        # Dropdown for explanations
        pair_options = optimal_df.apply(
            lambda r: f"{r['client_name']} ↔ {r['maid_id']} ({r['Final Score %']}%)", axis=1
        )
        selected_pair = st.selectbox("Select a Client–Maid Pair for Detailed Explanation", pair_options)
    
        if selected_pair:
            row = optimal_df.iloc[pair_options.tolist().index(selected_pair)]
            st.subheader(f"Explanation for {row['client_name']} ↔ {row['maid_id']}")
            st.write("**Household & Kids:**", row["Household & Kids Reason"])
            st.write("**Special Cases:**", row["Special Cases Reason"])
            st.write("**Pets:**", row["Pets Reason"])
            st.write("**Living:**", row["Living Reason"])
            st.write("**Nationality:**", row["Nationality Reason"])
            st.write("**Cuisine:**", row["Cuisine Reason"])
            st.write("**Bonus:**", row["Bonus Reasons"])
        
        # Save Tab 2 optimal matches in memory for later tabs
        st.session_state["optimal_df"] = optimal_df
        st.download_button(
            "Download Optimal Matches CSV",
            optimal_df.to_csv(index=False).encode("utf-8"),
            "optimal_matches.csv",
            "text/csv"
        )
    


    # ---------------- Tab 3: Customer Interface ----------------
    with tab3:
        st.write("### Try Your Own Preferences")
    
        # Input widgets
        c_household = st.selectbox("Household Type", ["unspecified", "baby", "many_kids", "baby_and_kids"])
        c_special = st.selectbox("Special Cases", ["unspecified", "elderly", "special_needs", "elderly_and_special"])
        c_pets = st.selectbox("Pet Type", ["unspecified", "cat", "dog", "both"])
        c_living = st.selectbox("Living Arrangement", [
            "unspecified", "private_room", "live_out+private_room",
            "private_room+abu_dhabi", "live_out+private_room+abu_dhabi"
        ])
        c_nationality = st.selectbox("Nationality Preference", [
            "any", "filipina", "ethiopian maid", "west african nationality", "indian"
        ])
        c_cuisine = st.multiselect("Cuisine Preference", ["lebanese", "khaleeji", "international"])
        cuisine_pref = "+".join(c_cuisine) if c_cuisine else "unspecified"
    
        # Button to run match
        if st.button("Find Best Maids"):
            client_row = {
                "clientmts_household_type": c_household,
                "clientmts_special_cases": c_special,
                "clientmts_pet_type": c_pets,
                "clientmts_living_arrangement": c_living,
                "clientmts_nationality_preference": c_nationality,
                "clientmts_cuisine_preference": cuisine_pref
            }
    
            results = []
            for _, maid_row in maids_df.iterrows():
                row = {**client_row, **maid_row.to_dict()}
                score, reasons, bonus_reasons = calculate_score(row)
                results.append({
                    "maid_id": maid_row["maid_id"],
                    "Final Score %": score,
                    **reasons,
                    "Bonus Reasons": ", ".join(bonus_reasons) if bonus_reasons else "None"
                })
    
            top_matches = sorted(results, key=lambda x: x["Final Score %"], reverse=True)[:3]
            top_df = pd.DataFrame(top_matches)
            st.dataframe(top_df)
    
            # Detailed explanations
            for match in top_matches:
                with st.expander(f"Maid {match['maid_id']} → {match['Final Score %']}%"):
                    st.write("**Household & Kids:**", match["Household & Kids Reason"])
                    st.write("**Special Cases:**", match["Special Cases Reason"])
                    st.write("**Pets:**", match["Pets Reason"])
                    st.write("**Living:**", match["Living Reason"])
                    st.write("**Nationality:**", match["Nationality Reason"])
                    st.write("**Cuisine:**", match["Cuisine Reason"])
                    st.write("**Bonus:**", match["Bonus Reasons"])

    # ---------------- Tab 4: Maid Profile Explorer ----------------
    with tab4:
        st.subheader("Maid Profile Explorer")
    
        # Deduplicate by maid_id
        maids_df = df.drop_duplicates(subset=["maid_id"]).copy()
        maids_df = maids_df.loc[:, ~maids_df.columns.duplicated()]
    
        # Detect maid-related columns (exclude irrelevant ones)
        maid_cols = [
            c for c in maids_df.columns
            if (c.startswith("maidmts_") or c.startswith("maidpref_") or c.startswith("maid_"))
            and c != "maidmts_at_hiring"
        ]
    
        # Detect language-related columns
        lang_cols = [c for c in maids_df.columns if c.startswith("maidspeaks_")]
    
        # Group explorer
        st.markdown("### Group Maids by Feature")
    
        feature_choice = st.selectbox(
            "Choose a feature to group by",
            maid_cols + ["maid_speaks_language"]
        )
    
        if feature_choice == "maid_speaks_language":
            # Handle language grouping separately
            for lang_col in lang_cols:
                lang_name = lang_col.replace("maidspeaks_", "").capitalize()
                maid_ids = maids_df.loc[maids_df[lang_col] == 1, "maid_id"].tolist()
    
                with st.expander(f"maid_speaks_language: {lang_name}"):
                    for mid in sorted(maid_ids):
                        if st.button(f"Maid {mid}", key=f"maid_lang_{lang_name}_{mid}"):
                            maid_row = maids_df[maids_df["maid_id"] == mid].iloc[0]
                            st.markdown(f"### Maid {maid_row['maid_id']}")
                            for col in maid_cols + lang_cols:
                                value = maid_row[col]
                                st.markdown(f"**{col.replace('_', ' ').capitalize()}:** {value}")
    
        else:
            # Normal grouping for all other features
            grouped = maids_df.groupby(feature_choice)["maid_id"].apply(list).reset_index()
    
            for _, row in grouped.iterrows():
                with st.expander(f"{feature_choice}: {row[feature_choice]}"):
                    for mid in sorted(row["maid_id"]):
                        if st.button(f"Maid {mid}", key=f"maid_{feature_choice}_{mid}"):
                            maid_row = maids_df[maids_df["maid_id"] == mid].iloc[0]
                            st.markdown(f"### Maid {maid_row['maid_id']}")
                            for col in maid_cols + lang_cols:
                                value = maid_row[col]
                                st.markdown(f"**{col.replace('_', ' ').capitalize()}:** {value}")


    # --------------------------------------------
    # Bridge: Prepare data for Summary Metrics tab
    # --------------------------------------------
    import os
    
    df, best_client_df = None, None
    
    # Try to reuse in-memory results from Tabs 1 and 2
    if "results_df" in locals() and "Final Score %" in results_df.columns:
        df = results_df.copy()
    
    if "optimal_df" in locals() and "Final Score %" in optimal_df.columns:
        best_client_df = optimal_df.copy()
    
    # ✅ Fallback: if app restarted, load from saved CSVs
    if df is None and os.path.exists("matching_results.csv"):
        df = pd.read_csv("matching_results.csv")
    if best_client_df is None and os.path.exists("optimal_matches.csv"):
        best_client_df = pd.read_csv("optimal_matches.csv")
    
    # ✅ Ensure numeric type for score columns
    if df is not None and "Final Score %" in df.columns:
        df["Final Score %"] = pd.to_numeric(df["Final Score %"], errors="coerce")
    if best_client_df is not None and "Final Score %" in best_client_df.columns:
        best_client_df["Final Score %"] = pd.to_numeric(best_client_df["Final Score %"], errors="coerce")
    
    # ✅ Standardize column name for summary code
    if df is not None and "Final Score %" in df.columns:
        df["match_score_pct"] = df["Final Score %"]
    if best_client_df is not None and "Final Score %" in best_client_df.columns:
        best_client_df["match_score_pct"] = best_client_df["Final Score %"]
    
    # ✅ Diagnostics
    st.write("Summary Metrics")
    st.write(f"Tagged: {len(df) if df is not None else 0}, Best: {len(best_client_df) if best_client_df is not None else 0}")


    # ---------------- Tab 5: Summary Metrics ----------------
    with tab5:
        st.subheader("Summary Metrics")
    
        # --- Safety: ensure datasets are available
        if df is None or best_client_df is None:
            st.warning("⚠️ Run Tab 1 (Matching Scores) and Tab 2 (Optimal Matches) before viewing Summary Metrics.")
        else:
            # ✅ Debug check (temporary)
            st.write(f"Tagged: {len(df)}, Best: {len(best_client_df)}")
    
            # --- Safety: ensure columns exist
            if "match_score_pct" not in df.columns or "match_score_pct" not in best_client_df.columns:
                st.error("Required column 'match_score_pct' not found. Please compute match scores first.")
            else:
                # ---------------- Averages ----------------
                avg_tagged = df["match_score_pct"].mean()
                avg_best = best_client_df["match_score_pct"].mean()
                delta = avg_best - avg_tagged
    
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Avg Tagged Match Score", f"{avg_tagged:.1f}%")
                    st.caption(
                        "Represents current placement quality across tagged assignments. "
                        "Lower averages indicate suboptimal client–maid pairings."
                    )
    
                with col2:
                    st.metric("Avg Best Match Score", f"{avg_best:.1f}%")
                    st.caption(
                        "Shows the achievable average if each client were paired with their highest-fit maid "
                        "based on the algorithmic matching logic."
                    )
    
                with col3:
                    st.metric("Potential Improvement", f"{delta:+.1f}%")
                    st.caption(
                        "The uplift margin between current and optimal alignment — a direct measure of operational headroom."
                    )
    
                # ---------------- Distribution ----------------
                st.markdown("### Distribution of Match Scores")
                import plotly.express as px, numpy as np
    
                # Ensure numeric just in case
                df["match_score_pct"] = pd.to_numeric(df["match_score_pct"], errors="coerce")
                best_client_df["match_score_pct"] = pd.to_numeric(best_client_df["match_score_pct"], errors="coerce")
    
                tagged_scores = df[["match_score_pct"]].assign(type="Tagged")
                best_scores = best_client_df[["match_score_pct"]].assign(type="Best")
                dist_data = pd.concat([tagged_scores, best_scores], ignore_index=True)
    
                # Diagnostic check (optional)
                st.write("Value counts by group:", dist_data["type"].value_counts())
    
                bins = np.arange(0, 110, 10)
                dist_data["bin"] = pd.cut(dist_data["match_score_pct"], bins=bins, right=False)
                grouped = (
                    dist_data.groupby(["bin", "type"]).size().reset_index(name="count")
                )
                grouped["percent"] = grouped.groupby("type")["count"].transform(lambda x: x / x.sum() * 100)
                grouped["bin"] = grouped["bin"].astype(str)
    
                fig = px.bar(
                    grouped,
                    x="bin",
                    y="percent",
                    color="type",
                    barmode="group",
                    color_discrete_map={"Tagged": "#1f77b4", "Best": "#6baed6"},
                    labels={"bin": "Match Score Range (%)", "percent": "Percentage of Clients", "type": "Group"},
                    title="Score Distribution: Tagged vs. Best Matches"
                )
                st.plotly_chart(fig, use_container_width=True)
    
                st.caption(
                    "The shift in distribution from darker to lighter blue illustrates potential gains achievable "
                    "through data-driven matching. More clients move from low-fit bands (<30%) into strong alignment zones."
                )
