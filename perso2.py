# app.py (version corrigée avec tableau simple)
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
from dateutil import tz
import plotly.graph_objects as go
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
import json

# ---------- CONFIG PAGE ----------
st.set_page_config(
    page_title="🌅 Checklist Spirituelle",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ---------- TEMPS ----------
TZ = tz.gettz("Europe/Paris")
def today_fr() -> date:
    return datetime.now(TZ).date()

TODAY = today_fr()
ISO_WEEK = TODAY.isocalendar().week
CURRENT_HOUR = datetime.now(TZ).hour

JOURS_FR = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]
def format_date_fr(d: date) -> str:
    return f"{JOURS_FR[d.weekday()]} {d.strftime('%d/%m/%Y')}"

# ---------- DB ----------
DATABASE_URL = "postgresql://postgres:nQNqqM4xfAc1qVYg@db.bzfexxxfiiioebxcjelr.supabase.co:5432/postgres?sslmode=require"

@st.cache_resource
def get_engine() -> Engine:
    return create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=5, max_overflow=5)

engine = get_engine()

# ---------- DONNÉES ----------
DEFAULT_OBJECTIVES = [
    {"name": "Lecture du Coran", "emoji": "📖", "category": "spirituel"},
    {"name": "Apprentissage du Coran", "emoji": "🧠", "category": "spirituel"},
    {"name": "Askar (dhikr)", "emoji": "🤲", "category": "spirituel"},
    {"name": "Gubsarba Huwal Messeh", "emoji": "💫", "category": "spirituel"},
    {"name": "Pas de sucre", "emoji": "🚫🍯", "category": "sante"},
    {"name": "10 000 pas", "emoji": "👟", "category": "sante"},
    {"name": "Prière à l'heure", "emoji": "🕌", "category": "spirituel"},
    {"name": "Méditation", "emoji": "🧘", "category": "bien-etre"},
    {"name": "Invocation du matin", "emoji": "🌅", "category": "spirituel"},
    {"name": "Invocation du soir", "emoji": "🌙", "category": "spirituel"},
]

# Démo minimale
HADITHS_DEMO = [
    {"arabic": "إِنَّمَا الأَعْمَالُ بِالنِّيَّاتِ","french":"Les actions ne valent que par les intentions","reference":"Sahih al-Bukhari"},
    {"arabic": "أَحَبُّ الأَعْمَالِ إِلَى اللَّهِ أَدْوَمُهَا وَإِنْ قَلَّ","french":"Les actions les plus aimées d'Allah sont les plus régulières, même si elles sont petites","reference":"Sahih al-Bukhari"},
    {"arabic": "مَنْ لَمْ يَشْكُرِ النَّاسَ لَمْ يَشْكُرِ اللَّهَ","french":"Celui qui ne remercie pas les gens ne remercie pas Allah","reference":"Sahih at-Tirmidhi"},
]
AYATS_DEMO = [
    {"arabic": "وَمَن يَتَّقِ اللَّهَ يَجْعَل لَّهُ مَخْرَجًا","french":"Et quiconque craint Allah, Il lui donnera une issue favorable","reference":"Coran 65:2"},
    {"arabic": "وَاللَّهُ مَعَ الصَّابِرِينَ","french":"Et Allah est avec les endurants","reference":"Coran 2:153"},
    {"arabic": "فَاذْكُرُونِي أَذْكُرْكُمْ","french":"Souvenez-vous de Moi, Je Me souviendrai de vous","reference":"Coran 2:152"},
]
HADITHS_365 = (HADITHS_DEMO * 122)[:365]
AYATS_365   = (AYATS_DEMO   * 122)[:365]

# ---------- SQL DDL ----------
def create_tables():
    """Créer toutes les tables nécessaires"""
    try:
        with engine.begin() as conn:
            # Table principale des objectifs
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS daily_objectives (
                    id SERIAL PRIMARY KEY,
                    date DATE NOT NULL,
                    objectif TEXT NOT NULL,
                    emoji TEXT DEFAULT '🎯',
                    category TEXT DEFAULT 'general',
                    mari BOOLEAN DEFAULT FALSE,
                    femme BOOLEAN DEFAULT FALSE,
                    mari_note TEXT DEFAULT '',
                    femme_note TEXT DEFAULT '',
                    semaine_iso INTEGER,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
            """))
            
            # Table des hadiths
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS hadiths (
                    id SERIAL PRIMARY KEY,
                    day_of_year INTEGER UNIQUE NOT NULL,
                    arabic TEXT NOT NULL,
                    french TEXT NOT NULL,
                    reference TEXT NOT NULL
                );
            """))
            
            # Table des ayats
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS ayats (
                    id SERIAL PRIMARY KEY,
                    day_of_year INTEGER UNIQUE NOT NULL,
                    arabic TEXT NOT NULL,
                    french TEXT NOT NULL,
                    reference TEXT NOT NULL
                );
            """))
            
            # Table des paramètres utilisateur
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS user_settings (
                    id SERIAL PRIMARY KEY,
                    user_type TEXT DEFAULT 'family',
                    show_mari BOOLEAN DEFAULT TRUE,
                    show_femme BOOLEAN DEFAULT TRUE,
                    notification_time TIME DEFAULT '06:00:00',
                    theme TEXT DEFAULT 'aurore',
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
            """))
            
    except Exception as e:
        st.error(f"Erreur création tables: {e}")

def migrate_database():
    """Migration sécurisée des colonnes"""
    try:
        with engine.begin() as conn:
            # Vérifier l'existence de la table
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'daily_objectives'
                );
            """))
            
            if not result.scalar():
                # La table n'existe pas, la créer
                create_tables()
                return
            
            # Vérifier les colonnes existantes
            result = conn.execute(text("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name = 'daily_objectives'
            """))
            existing_columns = [row[0] for row in result.fetchall()]
            
            # Ajouter les colonnes manquantes une par une
            columns_to_add = [
                ("emoji", "TEXT DEFAULT '🎯'"),
                ("category", "TEXT DEFAULT 'general'"),
                ("mari_note", "TEXT DEFAULT ''"),
                ("femme_note", "TEXT DEFAULT ''"),
                ("semaine_iso", "INTEGER")
            ]
            
            for col_name, col_def in columns_to_add:
                if col_name not in existing_columns:
                    try:
                        conn.execute(text(f"ALTER TABLE daily_objectives ADD COLUMN {col_name} {col_def}"))
                    except Exception:
                        pass  # Colonne existe déjà ou autre problème
            
            # Vérifier table user_settings
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'user_settings'
                );
            """))
            
            if not result.scalar():
                conn.execute(text("""
                    CREATE TABLE user_settings (
                        id SERIAL PRIMARY KEY,
                        user_type TEXT DEFAULT 'family',
                        show_mari BOOLEAN DEFAULT TRUE,
                        show_femme BOOLEAN DEFAULT TRUE,
                        notification_time TIME DEFAULT '06:00:00',
                        theme TEXT DEFAULT 'aurore',
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    )
                """))
                
    except Exception as e:
        st.error(f"Erreur de migration: {e}")

def seed_demo_if_empty():
    try:
        with engine.begin() as conn:
            h_count = conn.execute(text("SELECT COUNT(*) FROM hadiths")).scalar() or 0
            a_count = conn.execute(text("SELECT COUNT(*) FROM ayats")).scalar() or 0
            
            if h_count == 0:
                conn.execute(text("DELETE FROM hadiths"))
                for i, h in enumerate(HADITHS_365):
                    conn.execute(text("""
                        INSERT INTO hadiths (day_of_year, arabic, french, reference)
                        VALUES (:day_of_year, :arabic, :french, :reference)
                        ON CONFLICT (day_of_year) DO NOTHING
                    """), {"day_of_year": i+1, **h})
            
            if a_count == 0:
                conn.execute(text("DELETE FROM ayats"))
                for i, a in enumerate(AYATS_365):
                    conn.execute(text("""
                        INSERT INTO ayats (day_of_year, arabic, french, reference)
                        VALUES (:day_of_year, :arabic, :french, :reference)
                        ON CONFLICT (day_of_year) DO NOTHING
                    """), {"day_of_year": i+1, **a})
                    
    except Exception as e:
        st.error(f"Erreur seed: {e}")

def get_user_settings():
    try:
        with engine.begin() as conn:
            result = conn.execute(text("SELECT * FROM user_settings LIMIT 1")).mappings().first()
            if not result:
                conn.execute(text("""INSERT INTO user_settings (user_type, show_mari, show_femme) 
                                    VALUES ('family', TRUE, TRUE)"""))
                return {"show_mari": True, "show_femme": True, "user_type": "family"}
            return dict(result)
    except Exception:
        return {"show_mari": True, "show_femme": True, "user_type": "family"}

def update_user_settings(settings):
    try:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM user_settings"))
            conn.execute(text("""INSERT INTO user_settings (user_type, show_mari, show_femme) 
                                VALUES (:user_type, :show_mari, :show_femme)"""), settings)
        return True
    except Exception:
        return False

def load_today_data() -> pd.DataFrame:
    try:
        query = """
        SELECT objectif, emoji, category, mari, femme, mari_note, femme_note
        FROM daily_objectives 
        WHERE date = :d
        ORDER BY id
        """
        df = pd.read_sql(text(query), engine, params={"d": TODAY})
        
        if df.empty:
            # Retourner les objectifs par défaut
            return pd.DataFrame([{
                "objectif": obj["name"], 
                "emoji": obj["emoji"], 
                "category": obj["category"], 
                "mari": False, 
                "femme": False,
                "mari_note": "",
                "femme_note": ""
            } for obj in DEFAULT_OBJECTIVES])
        
        return df
        
    except Exception as e:
        st.error(f"Erreur de chargement: {e}")
        return pd.DataFrame([{
            "objectif": obj["name"], 
            "emoji": obj["emoji"], 
            "category": obj["category"], 
            "mari": False, 
            "femme": False,
            "mari_note": "",
            "femme_note": ""
        } for obj in DEFAULT_OBJECTIVES])

def save_today_data(df) -> bool:
    try:
        with engine.begin() as conn:
            # Supprimer les données existantes
            conn.execute(text("DELETE FROM daily_objectives WHERE date = :d"), {"d": TODAY})
            
            # Insérer les nouvelles données
            for _, row in df.iterrows():
                if row["objectif"].strip():
                    conn.execute(text("""
                        INSERT INTO daily_objectives 
                        (date, objectif, emoji, category, mari, femme, mari_note, femme_note, semaine_iso)
                        VALUES (:date, :objectif, :emoji, :category, :mari, :femme, :mari_note, :femme_note, :semaine_iso)
                    """), {
                        "date": TODAY,
                        "objectif": row["objectif"],
                        "emoji": row.get("emoji", "🎯"),
                        "category": row.get("category", "general"),
                        "mari": row.get("mari", False),
                        "femme": row.get("femme", False),
                        "mari_note": row.get("mari_note", ""),
                        "femme_note": row.get("femme_note", ""),
                        "semaine_iso": ISO_WEEK
                    })
        return True
    except Exception as e:
        st.error(f"Erreur sauvegarde: {e}")
        return False

def load_historical_data(days: int = 30) -> pd.DataFrame:
    try:
        start_date = TODAY - timedelta(days=days)
        q = text("SELECT * FROM daily_objectives WHERE date >= :d ORDER BY date DESC, id ASC")
        return pd.read_sql(q, engine, params={"d": start_date})
    except Exception:
        return pd.DataFrame()

def get_daily_hadith_and_ayat():
    day_of_year = TODAY.timetuple().tm_yday
    try:
        with engine.begin() as conn:
            h = conn.execute(text("SELECT arabic, french, reference FROM hadiths WHERE day_of_year = :d"), {"d": day_of_year}).mappings().first()
            a = conn.execute(text("SELECT arabic, french, reference FROM ayats WHERE day_of_year = :d"), {"d": day_of_year}).mappings().first()
        if not h: h = HADITHS_365[(day_of_year - 1) % len(HADITHS_365)]
        if not a: a = AYATS_365[(day_of_year - 1) % len(AYATS_365)]
        return h, a
    except Exception:
        return HADITHS_365[(day_of_year - 1) % len(HADITHS_365)], AYATS_365[(day_of_year - 1) % len(AYATS_365)]

# ---------- CSS ----------
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800&display=swap');
  @import url('https://fonts.googleapis.com/css2?family=Amiri:wght@400;700&display=swap');
  
  :root {
    --primary:#F59E0B; --secondary:#EF4444; --accent:#10B981; --bg:#FEF7ED; --card:#FFFFFF; --text:#1F2937; --muted:#6B7280;
    --shadow:0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -1px rgba(0,0,0,0.06);
    --shadow-lg:0 20px 25px -5px rgba(0,0,0,0.1), 0 10px 10px -5px rgba(0,0,0,0.04);
  }
  
  * { font-family: 'Inter', sans-serif !important; }
  body { background: var(--bg); color: var(--text); }
  
  .main-header {
    background: linear-gradient(135deg, var(--primary), var(--secondary));
    color: #fff;
    padding: 1.75rem;
    border-radius: 20px;
    text-align: center;
    box-shadow: var(--shadow-lg);
    margin-bottom: 1.25rem;
  }
  
  .wisdom-card {
    background: var(--card);
    border: 2px solid var(--accent);
    border-radius: 16px;
    padding: 1rem;
    margin: 0.5rem 0;
    box-shadow: var(--shadow);
  }
  
  .arabic-text {
    font-family: 'Amiri', serif !important;
    font-size: 1.25rem;
    text-align: right;
    direction: rtl;
    margin-bottom: 0.5rem;
    color: var(--primary);
    font-weight: 700;
    line-height: 1.6;
  }
  
  .french-text {
    font-size: 1rem;
    font-style: italic;
    margin-bottom: 0.25rem;
    color: var(--text);
    line-height: 1.4;
  }
  
  .reference {
    color: var(--muted);
    font-size: 0.9rem;
    text-align: right;
  }
  
  .wisdom-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.75rem;
    margin: 0.5rem 0;
  }
  
  .stat-card {
    background: var(--card);
    padding: 1rem;
    border-radius: 12px;
    text-align: center;
    box-shadow: var(--shadow);
    border-top: 3px solid var(--accent);
  }
  
  .stat-number {
    font-size: 2rem;
    font-weight: 700;
    color: var(--primary);
    margin-bottom: 0.25rem;
  }
  
  .stat-label {
    color: var(--muted);
    font-size: 0.9rem;
  }
  
  /* Styles pour le dataframe mobile */
  .stDataFrame {
    border: none !important;
    font-size: 1.1rem !important;
  }
  
  .stDataFrame > div {
    border: 1px solid #E5E7EB !important;
    border-radius: 12px !important;
    overflow: hidden !important;
  }
  
  /* Amélioration mobile pour les tableaux */
  @media (max-width: 768px) {
    .stDataFrame {
      font-size: 1rem !important;
    }
    
    .stDataFrame th {
      font-size: 0.95rem !important;
      padding: 0.75rem !important;
    }
    
    .stDataFrame td {
      font-size: 0.9rem !important;
      padding: 0.75rem !important;
    }
  }
  
  /* Catégories avec couleurs */
  .category-spirituel { border-left: 4px solid #8B5CF6 !important; }
  .category-sante { border-left: 4px solid #EF4444 !important; }
  .category-bien-etre { border-left: 4px solid #10B981 !important; }
  .category-general { border-left: 4px solid #F59E0B !important; }
  
  @media (max-width: 900px) {
    .wisdom-grid { grid-template-columns: 1fr; }
    .main-header { padding: 1.25rem; border-radius: 16px; }
  }
</style>
""", unsafe_allow_html=True)

# ---------- INIT DB ----------
with st.spinner("🔄 Initialisation de la base de données..."):
    try:
        create_tables()
        migrate_database()
        seed_demo_if_empty()
    except Exception as e:
        st.error(f"⚠ Problème lors de l'initialisation: {e}")

# ---------- SETTINGS ----------
user_settings = get_user_settings()

# ---------- HEADER ----------
st.markdown(f"""
<div class="main-header">
  <h1 style="margin:0; font-size:2rem;">🌅 Joker Family</h1>
  <p style="margin:.5rem 0 0 0; opacity:.9;">{format_date_fr(TODAY)} • Semaine {ISO_WEEK}</p>
</div>
""", unsafe_allow_html=True)

# ---------- PROGRESS DU JOUR ----------
today_df = load_today_data()
if not today_df.empty:
    mari_done = today_df["mari"].sum() if user_settings["show_mari"] else 0
    femme_done = today_df["femme"].sum() if user_settings["show_femme"] else 0
    total_obj = len(today_df)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-number">{total_obj}</div>
            <div class="stat-label">Objectifs</div>
        </div>
        """, unsafe_allow_html=True)
    
    if user_settings["show_mari"]:
        with col2:
            mari_pct = int((mari_done / total_obj) * 100) if total_obj > 0 else 0
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-number">{mari_pct}%</div>
                <div class="stat-label">👨 Mari ({mari_done}/{total_obj})</div>
            </div>
            """, unsafe_allow_html=True)
    
    if user_settings["show_femme"]:
        with col3:
            femme_pct = int((femme_done / total_obj) * 100) if total_obj > 0 else 0
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-number">{femme_pct}%</div>
                <div class="stat-label">👩 Femme ({femme_done}/{total_obj})</div>
            </div>
            """, unsafe_allow_html=True)

# ---------- SAGESSE DU JOUR ----------
hadith, ayat = get_daily_hadith_and_ayat()
st.markdown(f"""
<div class="wisdom-grid">
  <div class="wisdom-card">
    <div style="text-align:center;color:var(--accent);font-weight:600;margin-bottom:.5rem;">📿 Hadith du jour</div>
    <div class="arabic-text">{hadith['arabic']}</div>
    <div class="french-text">« {hadith['french']} »</div>
    <div class="reference">— {hadith['reference']}</div>
  </div>
  <div class="wisdom-card">
    <div style="text-align:center;color:var(--secondary);font-weight:600;margin-bottom:.5rem;">📖 Ayat du jour</div>
    <div class="arabic-text">{ayat['arabic']}</div>
    <div class="french-text">« {ayat['french']} »</div>
    <div class="reference">— {ayat['reference']}</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ---------- OBJECTIFS DU JOUR - VERSION MOBILE SIMPLE ----------
st.markdown("## 🎯 Objectifs du jour")

if not today_df.empty:
    # Configuration simple pour mobile - seulement objectif et cases à cocher
    columns_config = {
        "objectif": st.column_config.TextColumn("📝 Objectif", width="large")
    }
    
    if user_settings["show_mari"]:
        columns_config["mari"] = st.column_config.CheckboxColumn("👨", width="small")
    
    if user_settings["show_femme"]:
        columns_config["femme"] = st.column_config.CheckboxColumn("👩", width="small")
    
    # Colonnes à afficher (simplifiées)
    display_columns = ["objectif"]
    if user_settings["show_mari"]:
        display_columns.append("mari")
    if user_settings["show_femme"]:
        display_columns.append("femme")
    
    # Éditeur de données simplifié
    edited_df = st.data_editor(
        today_df[display_columns],
        column_config=columns_config,
        num_rows="dynamic",
        use_container_width=True,
        key="objectives_editor",
        hide_index=True
    )
    
    # Boutons d'action en version mobile
    st.markdown("### Actions")
    
    # Première ligne de boutons
    col1, col2 = st.columns(2)
    with col1:
        if st.button("➕ Ajouter objectifs par défaut", use_container_width=True):
            # Ajouter les objectifs par défaut
            default_df = pd.DataFrame([{
                "objectif": obj["name"], 
                "emoji": obj["emoji"], 
                "category": obj["category"], 
                "mari": False, 
                "femme": False,
                "mari_note": "",
                "femme_note": ""
            } for obj in DEFAULT_OBJECTIVES])
            
            # Fusionner avec les données existantes
            combined_df = pd.concat([today_df, default_df], ignore_index=True)
            combined_df = combined_df.drop_duplicates(subset=["objectif"], keep="first")
            
            if save_today_data(combined_df):
                st.success("✅ Objectifs par défaut ajoutés!")
                st.rerun()
    
    with col2:
        if st.button("🗑️ Effacer tous les objectifs", use_container_width=True):
            try:
                with engine.begin() as conn:
                    conn.execute(text("DELETE FROM daily_objectives WHERE date = :d"), {"d": TODAY})
                st.success("🗑️ Objectifs effacés!")
                st.rerun()
            except Exception as e:
                st.error(f"Erreur: {e}")
    
    # Bouton de sauvegarde principal
    st.markdown("---")
    if st.button("💾 **SAUVEGARDER LES MODIFICATIONS**", type="primary", use_container_width=True):
        # Ajouter les colonnes manquantes avec des valeurs par défaut
        if "emoji" not in edited_df.columns:
            edited_df["emoji"] = "🎯"
        if "category" not in edited_df.columns:
            edited_df["category"] = "general"
        if "mari_note" not in edited_df.columns:
            edited_df["mari_note"] = ""
        if "femme_note" not in edited_df.columns:
            edited_df["femme_note"] = ""
        if "mari" not in edited_df.columns:
            edited_df["mari"] = False
        if "femme" not in edited_df.columns:
            edited_df["femme"] = False
            
        if save_today_data(edited_df):
            st.success("✅ Objectifs sauvegardés avec succès!")
            st.balloons()
            st.rerun()

# ---------- REPORTING ----------
st.markdown("## 📈 Reporting et Analyse")
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📅 Historique", "📊 Graphiques", "🏆 Stats", "⚙️ Paramètres", "📱 Export"])

with tab1:
    st.subheader("📅 Historique récent")
    days_filter = st.selectbox("Période", [7, 14, 30, 60], index=2)
    historical_df = load_historical_data(days_filter)
    
    if not historical_df.empty:
        # Afficher les données récentes
        recent_data = historical_df.head(50)  # Limiter à 50 entrées
        
        # Configuration pour l'affichage
        display_config = {
            "date": st.column_config.DateColumn("📅 Date"),
            "objectif": st.column_config.TextColumn("🎯 Objectif"),
            "mari": st.column_config.CheckboxColumn("👨 Mari"),
            "femme": st.column_config.CheckboxColumn("👩 Femme"),
            "category": st.column_config.TextColumn("🏷️ Catégorie")
        }
        
        st.dataframe(
            recent_data[["date", "objectif", "mari", "femme", "category"]],
            column_config=display_config,
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("Aucune donnée historique disponible")

with tab2:
    st.subheader("📊 Évolution des performances")
    period = st.selectbox("Période d'analyse", [7, 14, 30, 60, 90], index=2, key="graph_period")
    historical_df = load_historical_data(period)
    
    if not historical_df.empty and len(historical_df) > 0:
        # Graphique d'évolution
        daily_stats = historical_df.groupby("date").agg({
            "mari": "sum",
            "femme": "sum",
            "objectif": "count"
        }).reset_index()
        
        fig = go.Figure()
        if user_settings["show_mari"]:
            fig.add_trace(go.Scatter(
                x=daily_stats["date"], 
                y=(daily_stats["mari"] / daily_stats["objectif"] * 100),
                name="👨 Mari (%)", 
                line=dict(color="#3B82F6")
            ))
        if user_settings["show_femme"]:
            fig.add_trace(go.Scatter(
                x=daily_stats["date"], 
                y=(daily_stats["femme"] / daily_stats["objectif"] * 100),
                name="👩 Femme (%)", 
                line=dict(color="#EF4444")
            ))
        
        fig.update_layout(
            title="Évolution du taux de réussite (%)",
            xaxis_title="Date",
            yaxis_title="Pourcentage",
            margin=dict(l=10,r=10,t=40,b=10),
            height=400
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Pas assez de données pour générer des graphiques")

with tab3:
    st.subheader("🏆 Statistiques détaillées")
    
    # Période de statistiques
    stats_period = st.selectbox("Période", [7, 14, 30, 60, 90], index=2, key="stats_period")
    historical_df = load_historical_data(stats_period)
    
    if not historical_df.empty:
        # Stats globales
        col1, col2, col3, col4 = st.columns(4)
        
        total_days = historical_df["date"].nunique()
        total_objectives = len(historical_df)
        
        with col1:
            st.metric("🗓️ Jours analysés", total_days)
        with col2:
            st.metric("🎯 Total objectifs", total_objectives)
        
        if user_settings["show_mari"]:
            mari_success = historical_df["mari"].sum()
            mari_rate = (mari_success / total_objectives * 100) if total_objectives > 0 else 0
            with col3:
                st.metric("👨 Taux Mari", f"{mari_rate:.1f}%")
        
        if user_settings["show_femme"]:
            femme_success = historical_df["femme"].sum()
            femme_rate = (femme_success / total_objectives * 100) if total_objectives > 0 else 0
            with col4:
                st.metric("👩 Taux Femme", f"{femme_rate:.1f}%")
        
        # Stats par catégorie
        if "category" in historical_df.columns:
            st.subheader("📊 Performance par catégorie")
            cat_stats = historical_df.groupby("category").agg({
                "mari": ["count", "sum", "mean"],
                "femme": ["count", "sum", "mean"]
            }).round(3)
            
            for category in historical_df["category"].unique():
                cat_data = historical_df[historical_df["category"] == category]
                total_cat = len(cat_data)
                
                with st.container():
                    st.write(f"**{category.title()}** ({total_cat} objectifs)")
                    col1, col2 = st.columns(2)
                    
                    if user_settings["show_mari"]:
                        mari_cat_success = cat_data["mari"].sum()
                        mari_cat_rate = (mari_cat_success / total_cat * 100) if total_cat > 0 else 0
                        with col1:
                            st.metric(f"👨 {category}", f"{mari_cat_rate:.1f}%", f"{mari_cat_success}/{total_cat}")
                    
                    if user_settings["show_femme"]:
                        femme_cat_success = cat_data["femme"].sum()
                        femme_cat_rate = (femme_cat_success / total_cat * 100) if total_cat > 0 else 0
                        with col2:
                            st.metric(f"👩 {category}", f"{femme_cat_rate:.1f}%", f"{femme_cat_success}/{total_cat}")
        
        # Séries de réussite
        st.subheader("🔥 Séries de réussite")
        daily_completion = historical_df.groupby("date").agg({
            "objectif": "count",
            "mari": "sum",
            "femme": "sum"
        }).reset_index()
        
        # Calculer les séries
        daily_completion["mari_perfect"] = daily_completion["mari"] == daily_completion["objectif"]
        daily_completion["femme_perfect"] = daily_completion["femme"] == daily_completion["objectif"]
        
        # Série actuelle
        latest_days = daily_completion.sort_values("date", ascending=False).head(7)
        
        col1, col2 = st.columns(2)
        if user_settings["show_mari"]:
            mari_streak = 0
            for _, day in latest_days.iterrows():
                if day["mari_perfect"]:
                    mari_streak += 1
                else:
                    break
            with col1:
                st.metric("🔥 Série actuelle Mari", f"{mari_streak} jour(s)")
        
        if user_settings["show_femme"]:
            femme_streak = 0
            for _, day in latest_days.iterrows():
                if day["femme_perfect"]:
                    femme_streak += 1
                else:
                    break
            with col2:
                st.metric("🔥 Série actuelle Femme", f"{femme_streak} jour(s)")
    else:
        st.info("Pas assez de données pour calculer les statistiques.")

with tab4:
    st.subheader("⚙️ Paramètres de l'application")
    
    # Configuration utilisateur
    st.write("**👥 Configuration utilisateur**")
    user_type = st.selectbox(
        "Type d'utilisation",
        ["family", "individual_mari", "individual_femme"],
        index=0 if user_settings.get("user_type") == "family" else (1 if user_settings.get("user_type") == "individual_mari" else 2)
    )
    
    show_mari = user_settings["show_mari"]
    show_femme = user_settings["show_femme"]
    
    if user_type == "family":
        show_mari = st.checkbox("Afficher la colonne Mari", value=user_settings["show_mari"])
        show_femme = st.checkbox("Afficher la colonne Femme", value=user_settings["show_femme"])
    elif user_type == "individual_mari":
        show_mari = True
        show_femme = False
        st.info("Mode individuel - Mari uniquement")
    else:  # individual_femme
        show_mari = False
        show_femme = True
        st.info("Mode individuel - Femme uniquement")
    
    # Sauvegarder les paramètres
    if st.button("💾 Sauvegarder les paramètres"):
        new_settings = {
            "user_type": user_type,
            "show_mari": show_mari,
            "show_femme": show_femme
        }
        if update_user_settings(new_settings):
            st.success("✅ Paramètres sauvegardés!")
            st.rerun()
    
    st.write("---")
    
    # Import JSON
    st.write("**📥 Import de données authentiques**")
    st.caption("Format JSON : {'hadiths':[{arabic,french,reference}], 'ayats':[{arabic,french,reference}]}")
    json_file = st.file_uploader("Fichier JSON", type=["json"], key="import_json")
    if json_file is not None:
        if st.button("📥 Importer"):
            try:
                payload = json.loads(json_file.getvalue().decode("utf-8"))
                hadiths = payload.get("hadiths", [])[:365]
                ayats = payload.get("ayats", [])[:365]
                
                if hadiths or ayats:
                    with engine.begin() as conn:
                        if hadiths:
                            conn.execute(text("TRUNCATE TABLE hadiths RESTART IDENTITY"))
                            conn.execute(
                                text("""INSERT INTO hadiths (day_of_year, arabic, french, reference)
                                        VALUES (:day_of_year, :arabic, :french, :reference)"""),
                                [{"day_of_year": i+1, **h} for i, h in enumerate(hadiths)]
                            )
                        if ayats:
                            conn.execute(text("TRUNCATE TABLE ayats RESTART IDENTITY"))
                            conn.execute(
                                text("""INSERT INTO ayats (day_of_year, arabic, french, reference)
                                        VALUES (:day_of_year, :arabic, :french, :reference)"""),
                                [{"day_of_year": i+1, **a} for i, a in enumerate(ayats)]
                            )
                    st.success(f"✅ Import réussi: {len(hadiths)} hadith(s) & {len(ayats)} ayat(s).")
                    st.rerun()
                else:
                    st.error("Aucune donnée trouvée dans le fichier")
            except Exception as e:
                st.error(f"Erreur d'import: {e}")
    
    st.write("---")
    
    # Réinitialisation
    st.write("**🔄 Réinitialisation**")
    if st.button("🗑️ Supprimer toutes les données", type="secondary"):
        if st.button("⚠️ Confirmer la suppression", type="secondary"):
            try:
                with engine.begin() as conn:
                    conn.execute(text("TRUNCATE TABLE daily_objectives RESTART IDENTITY"))
                st.success("🗑️ Toutes les données ont été supprimées")
                st.rerun()
            except Exception as e:
                st.error(f"Erreur: {e}")

with tab5:
    st.subheader("📱 Export et Sauvegarde")
    
    # Export CSV
    export_period = st.selectbox("Période d'export", [30, 60, 90, 180, 365], index=2)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📊 Exporter CSV complet"):
            historical_df = load_historical_data(export_period)
            if not historical_df.empty:
                csv = historical_df.to_csv(index=False, encoding='utf-8')
                st.download_button(
                    "💾 Télécharger CSV",
                    csv,
                    f"checklist_export_{TODAY.isoformat()}.csv",
                    "text/csv"
                )
            else:
                st.info("Aucune donnée à exporter")
    
    with col2:
        if st.button("📈 Exporter rapport résumé"):
            historical_df = load_historical_data(export_period)
            if not historical_df.empty:
                # Créer un rapport résumé
                summary = {
                    "periode": f"{export_period} derniers jours",
                    "total_jours": historical_df["date"].nunique(),
                    "total_objectifs": len(historical_df),
                    "taux_mari": f"{(historical_df['mari'].sum() / len(historical_df) * 100):.1f}%" if len(historical_df) > 0 else "0%",
                    "taux_femme": f"{(historical_df['femme'].sum() / len(historical_df) * 100):.1f}%" if len(historical_df) > 0 else "0%"
                }
                
                rapport = f"""
# Rapport Checklist Spirituelle
**Période:** {summary['periode']}
**Généré le:** {format_date_fr(TODAY)}

## Résumé
- **Jours analysés:** {summary['total_jours']}
- **Total objectifs:** {summary['total_objectifs']}
- **Taux de réussite Mari:** {summary['taux_mari']}
- **Taux de réussite Femme:** {summary['taux_femme']}

## Détails par catégorie
"""
                if "category" in historical_df.columns:
                    for cat in historical_df["category"].unique():
                        cat_data = historical_df[historical_df["category"] == cat]
                        mari_rate = (cat_data["mari"].sum() / len(cat_data) * 100) if len(cat_data) > 0 else 0
                        femme_rate = (cat_data["femme"].sum() / len(cat_data) * 100) if len(cat_data) > 0 else 0
                        rapport += f"\n**{cat.title()}:** Mari {mari_rate:.1f}% - Femme {femme_rate:.1f}%"
                
                st.download_button(
                    "📄 Télécharger rapport",
                    rapport,
                    f"rapport_checklist_{TODAY.isoformat()}.md",
                    "text/markdown"
                )
            else:
                st.info("Aucune donnée pour le rapport")
    
    # Informations système
    st.write("---")
    st.write("**ℹ️ Informations système**")
    st.info(f"""
    - **Dernière mise à jour:** {datetime.now(TZ).strftime('%H:%M:%S')}
    - **Heure actuelle:** {CURRENT_HOUR}h
    - **Réinitialisation:** {"✅ Active (minuit)" if 0 <= CURRENT_HOUR < 1 else "⏰ Prochaine à minuit"}
    - **Fuseau horaire:** Europe/Paris
    """)

# ---------- FOOTER ----------
st.markdown("---")
st.markdown(f"""
<div style="text-align:center;padding:1rem;opacity:.75;">
  <p>🌅 Checklist Spirituelle • Version Mobile Optimisée</p>
  <p>Dernière mise à jour: {datetime.now(TZ).strftime('%H:%M:%S')}</p>
</div>
""", unsafe_allow_html=True)