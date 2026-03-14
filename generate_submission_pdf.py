"""
generate_submission_pdf.py
==========================
Generates the RosterIQ Submission Documentation PDF.
Compatible with both old `fpdf` and new `fpdf2`.
Run: python generate_submission_pdf.py
Output: rosteriq_submission_report.pdf in the project root.
"""

from fpdf import FPDF
from datetime import datetime
import os

# ── Paths ─────────────────────────────────────────────────────────────────────
BRAIN_DIR = r"C:\Users\Atharv Priyadarshi\.gemini\antigravity\brain\6d608ce2-3677-4566-9a00-24fb8e969fdb"
IMG_SYSTEM_ARCH   = os.path.join(BRAIN_DIR, "system_architecture_1773502773316.png")
IMG_MEMORY_ARCH   = os.path.join(BRAIN_DIR, "memory_architecture_1773502794487.png")
IMG_LG_FLOW       = os.path.join(BRAIN_DIR, "langgraph_flow_1773502855818.png") 
IMG_DATA_PIPELINE = os.path.join(BRAIN_DIR, "data_pipeline_1773502875462.png")
OUTPUT_PATH = r"C:\Users\Atharv Priyadarshi\Documents\Healthcare-roster-agent\rosteriq_submission_report.pdf"

# ── Colors ────────────────────────────────────────────────────────────────────
DARK_BG    = (14, 17, 23)
WHITE      = (255, 255, 255)
BLUE       = (40, 100, 200)
GREEN      = (34, 139, 80)
PURPLE     = (110, 70, 200)
ORANGE     = (210, 100, 30)
TEXT_DARK  = (20, 20, 30)
TABLE_HDR  = (40, 70, 120)
TABLE_ALT  = (242, 244, 250)
GRAY_TEXT  = (100, 100, 120)


class PDF(FPDF):
    def header(self):
        if self.page_no() == 1:
            return
        self.set_fill_color(*DARK_BG)
        self.rect(0, 0, 210, 12, 'F')
        self.set_font('Arial', 'B', 8)
        self.set_text_color(*WHITE)
        self.set_xy(15, 2)
        self.cell(90, 7, 'RosterIQ - Submission Documentation Report')
        self.set_x(105)
        self.cell(90, 7, 'HiLabs x Cognizance 2026', align='R')
        self.set_y(15)
        self.set_text_color(*TEXT_DARK)

    def footer(self):
        pass  # No footer

    def banner(self):
        self.set_fill_color(*DARK_BG)
        self.rect(0, 0, 210, 50, 'F')
        self.set_text_color(*WHITE)
        self.set_font('Arial', 'B', 24)
        self.set_xy(15, 10)
        self.cell(0, 12, 'RosterIQ Intelligence', ln=True)
        self.set_font('Arial', '', 13)
        self.set_xy(15, 24)
        self.cell(0, 8, 'Autonomous Provider Roster Intelligence Agent', ln=True)
        self.set_font('Arial', 'I', 10)
        self.set_xy(15, 34)
        self.cell(0, 7, 'HiLabs Challenge @ Cognizance 2026  |  Submission Documentation Report', ln=True)
        self.set_xy(15, 43)
        self.cell(0, 6, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True)
        self.set_y(54)
        self.set_text_color(*TEXT_DARK)

    def section(self, num, title, color=None):
        if color is None:
            color = BLUE
        self.ln(4)
        self.set_fill_color(*color)
        self.set_text_color(*WHITE)
        self.set_font('Arial', 'B', 13)
        self.cell(0, 10, f'  {num}  {title}', ln=True, fill=True)
        self.set_text_color(*TEXT_DARK)
        self.ln(2)

    def sub(self, title):
        self.ln(3)
        self.set_font('Arial', 'B', 11)
        self.set_text_color(*BLUE)
        self.cell(0, 8, title, ln=True)
        self.set_text_color(*TEXT_DARK)

    def body(self, text):
        self.set_font('Arial', '', 9.5)
        self.set_text_color(*TEXT_DARK)
        self.multi_cell(0, 5.5, text)
        self.ln(1)

    def bullet(self, text, indent=5):
        self.set_font('Arial', '', 9.5)
        self.set_text_color(*TEXT_DARK)
        self.set_x(self.l_margin + indent)
        self.cell(5, 5.5, chr(149))
        self.multi_cell(0, 5.5, text)

    def code(self, text):
        self.set_fill_color(28, 30, 40)
        self.set_text_color(180, 220, 180)
        self.set_font('Courier', '', 7.5)
        self.multi_cell(0, 5, text, fill=True)
        self.set_text_color(*TEXT_DARK)
        self.ln(2)

    def table(self, headers, rows, widths, hdr_color=None):
        if hdr_color is None:
            hdr_color = TABLE_HDR
        self.set_font('Arial', 'B', 9)
        self.set_fill_color(*hdr_color)
        self.set_text_color(*WHITE)
        for i, h in enumerate(headers):
            self.cell(widths[i], 8, h, fill=True)
        self.ln()
        self.set_font('Arial', '', 8.5)
        self.set_text_color(*TEXT_DARK)
        for ri, row in enumerate(rows):
            fill = ri % 2 == 1
            self.set_fill_color(*TABLE_ALT) if fill else self.set_fill_color(255, 255, 255)
            for ci, val in enumerate(row):
                self.cell(widths[ci], 7, str(val)[:80], fill=True)
            self.ln()
        self.ln(2)

    def kpi_row(self, items):
        w = (210 - 40) / len(items)
        y = self.get_y()
        for i, (label, value, color) in enumerate(items):
            x = 20 + i * w
            self.set_fill_color(*color)
            self.rect(x, y, w - 3, 18, 'F')
            self.set_text_color(*WHITE)
            self.set_font('Arial', '', 8)
            self.set_xy(x + 2, y + 2)
            self.cell(w - 5, 5, label)
            self.set_font('Arial', 'B', 13)
            self.set_xy(x + 2, y + 8)
            self.cell(w - 5, 8, value)
        self.set_y(y + 22)
        self.set_text_color(*TEXT_DARK)

    def img(self, path, caption, w=168):
        if not os.path.exists(path):
            self.body(f'[Architecture image: {os.path.basename(path)}]')
            return
        x = (210 - w) / 2
        self.image(path, x=x, w=w)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(*GRAY_TEXT)
        self.cell(0, 6, caption, ln=True, align='C')
        self.set_text_color(*TEXT_DARK)
        self.ln(3)


# ─────────────────────────────────────────────────────────────────

def build():
    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.set_margins(20, 20, 20)

    # ── PAGE 1: COVER ──────────────────────────────────────────────
    pdf.add_page()
    pdf.banner()

    pdf.set_font('Arial', 'B', 11)
    pdf.set_text_color(*BLUE)
    pdf.cell(0, 7, 'Prepared for: HiLabs Challenge Judges', ln=True)
    pdf.set_text_color(*TEXT_DARK)
    pdf.ln(3)

    pdf.kpi_row([
        ('Knowledge Items', '40+',  PURPLE),
        ('Memory Types',    '3',    BLUE),
        ('Procedures',      '4',    GREEN),
        ('Visualizations',  '5',    ORANGE),
    ])
    pdf.ln(5)
    pdf.body('Tech Stack: LangGraph  .  Gemini 2.0 Flash  .  DuckDB  .  ChromaDB  .  SQLite  .  Streamlit  .  Plotly  .  Tavily  .  fpdf2')
    pdf.ln(5)

    toc = [
        ('1', 'Executive Summary'),
        ('2', 'Problem Approach & Scoping'),
        ('3', 'Overall System Architecture'),
        ('4', 'LangGraph Agent Execution Flow'),
        ('5', 'Data Layer & Tool Integration'),
        ('6', 'Memory Architecture - Deep Dive'),
        ('  6.1', 'Episodic Memory'),
        ('  6.2', 'Procedural Memory'),
        ('  6.3', 'Semantic Memory'),
        ('7', 'Innovations & Novel Design Patterns'),
        ('8', 'Bonus Challenges Implemented'),
        ('9', 'Challenges & Learnings'),
        ('10', 'Appendix: Technology Stack'),
    ]
    pdf.set_font('Arial', 'B', 11)
    pdf.set_text_color(*BLUE)
    pdf.cell(0, 8, 'Table of Contents', ln=True)
    pdf.set_text_color(*TEXT_DARK)
    pdf.set_font('Arial', '', 10)
    for n, t in toc:
        pdf.cell(18, 6, n)
        pdf.cell(0, 6, t, ln=True)

    # ── PAGE 2: EXECUTIVE SUMMARY ──────────────────────────────────
    pdf.add_page()
    pdf.section('1', 'Executive Summary')
    pdf.body(
        'RosterIQ is an autonomous, memory-driven AI agent designed to help healthcare payer operations '
        'teams diagnose and resolve provider roster pipeline failures at scale. Operating over two '
        'interlinked operational datasets -- file-level pipeline records (CSV 1) and monthly market '
        'transaction metrics (CSV 2) -- the agent maintains three distinct forms of persistent memory, '
        'uses a multi-tool suite for analytics and external research, and surfaces insights through a '
        'rich, interactive Streamlit web interface.'
    )
    pdf.body(
        'The system was built ground-up in 36 hours for the HiLabs Challenge at Cognizance 2026, '
        'implementing all three required memory types, multi-agent routing via LangGraph, an in-memory '
        'DuckDB analytics engine with cross-table joins, Plotly visualizations, Tavily-powered web '
        'search, and a proactive background monitoring thread.'
    )
    pdf.ln(2)
    pdf.table(
        ['Metric', 'Value'],
        [
            ['Domain Knowledge Items (Semantic KB)', '40+ items across 10 categories'],
            ['Persistent Memory Types', '3 (Episodic, Procedural, Semantic)'],
            ['Named Diagnostic Procedures', '4 (triage, market, retry analysis, bottleneck scan)'],
            ['Storage Backends', '3 (SQLite structured, ChromaDB vector, SQLite-WAL checkpoints)'],
            ['Visualization Types', '5 (market trend, stuck tracker, anomaly, correlation, PDF)'],
            ['Web Search Templates', '4 (validation failure, CMS rules, LOB compliance, provider)'],
            ['Specialist Sub-Agents', '2 (Pipeline Health Agent + Market Analytics Agent)'],
            ['Bonus Challenges Implemented', '3 of 3 (Proactive Monitoring, Multi-Agent, Root Cause)'],
        ],
        [85, 85],
    )

    # ── PAGE 3: PROBLEM APPROACH ───────────────────────────────────
    pdf.add_page()
    pdf.section('2', 'Problem Approach & Scoping')
    pdf.sub('2.1  Interpreting the Problem')
    pdf.body(
        'The fundamental challenge was not just building a chatbot over CSVs. The problem statement '
        'placed 35% weight on the memory architecture. This shaped the entire design philosophy: '
        '"Build memory first; intelligence second."'
    )
    pdf.body('The three memory types map directly to how an expert operations analyst thinks:')
    pdf.table(
        ['Memory Type', 'Analyst Analogy'],
        [
            ['Episodic',    '"I investigated this org last Tuesday -- it was stuck in DART_REVIEW."'],
            ['Procedural',  '"My standard triage: rank by Red flags x3, then time stuck x2."'],
            ['Semantic',    '"DART_GEN > 3x average almost always means a data volume spike."'],
        ],
        [38, 132],
    )
    pdf.sub('2.2  Dataset Understanding')
    pdf.bullet(
        'CSV 1 -- roster_processing_details.csv (File-Level): Each row is one Roster Operation (RO) '
        'moving through 7 pipeline stages. Every stage has actual and historical average durations, '
        'enabling deviation computation without external benchmarks.'
    )
    pdf.bullet(
        'CSV 2 -- aggregated_operational_metrics.csv (Market-Level): Monthly aggregate success rates '
        'by state. SCS_PERCENT < 95% triggers investigation. A lagging indicator relative to CSV 1.'
    )
    pdf.ln(2)
    pdf.body(
        'Most important analytical insight: the CSV1 -> CSV2 causal chain. File-level failures '
        '(Red flags, IS_STUCK, IS_FAILED) in CSV 1 are the CAUSE; market SCS_PERCENT drops in CSV 2 '
        'are the RESULT. The agent was designed to trace this chain in both directions.'
    )
    pdf.sub('2.3  Scoping Decisions (36-Hour Constraint)')
    for item in [
        'Full three-layer memory architecture with all persistent stores',
        'Multi-agent LangGraph graph with LLM supervisor routing',
        'Cross-table join analytics via DuckDB in-memory engine',
        'All 5 required visualization types (Plotly)',
        'Web search integration with semantic KB enrichment (Tavily)',
        'Proactive background monitoring thread (Bonus Challenge)',
        'Corporate PDF report generation with fpdf2',
        'Multi-session support with session switcher',
    ]:
        pdf.bullet(item)

    # ── PAGE 4: SYSTEM ARCHITECTURE ────────────────────────────────
    pdf.add_page()
    pdf.section('3', 'Overall System Architecture', BLUE)
    pdf.body(
        'The system is organized into three tiers: Presentation (Streamlit), Intelligence '
        '(LangGraph + ProactiveMonitor), and Data (DuckDB + Memory Stores + External APIs).'
    )
    pdf.img(IMG_SYSTEM_ARCH, 'Figure 1 -- RosterIQ Overall System Architecture (3-Tier)')
    pdf.sub('Tier 1 -- Presentation Layer (Streamlit)')
    pdf.body(
        'The Streamlit application (app.py) provides: chat interface with streaming responses, sidebar '
        'with live alerts, episodic memory viewer, operational diff (ChangeDetector), KPI snapshot, '
        'session switcher, and PDF export. A smart pre-agent query routing layer provides instant '
        'visualization responses without invoking the full LangGraph graph.'
    )
    pdf.sub('Tier 2 -- Intelligence Layer (LangGraph)')
    pdf.body(
        'LangGraph StateGraph with 5 nodes: START -> memory_loader -> supervisor -> '
        '[pipeline_agent | market_agent] -> memory_writer -> END. SqliteSaver checkpointer '
        'persists full graph state to roster_iq_threads.db after every node.'
    )
    pdf.sub('Tier 3 -- Data Layer')
    pdf.body(
        'DuckDB (in-memory analytics over CSVs), ChromaDB (3 vector collections), '
        'SQLite (structured interaction log), Tavily API (web search), and Google Gemini 2.0 Flash (LLM).'
    )

    # ── PAGE 5: LANGGRAPH FLOW ─────────────────────────────────────
    pdf.add_page()
    pdf.section('4', 'LangGraph Agent Execution Flow', BLUE)
    pdf.img(IMG_LG_FLOW, 'Figure 2 -- LangGraph State Machine Execution Flow')
    pdf.sub('Node 1 -- memory_loader_node')
    pdf.body(
        'Before any data analysis, this node injects all three memory types into the agent state: '
        'episodic context (last 3 chat turns via get_history), semantic KB hits (top-3 ChromaDB cosine '
        'matches), change summary (ChangeDetector), loaded procedure names + versions, and active alerts.'
    )
    pdf.sub('Node 2 -- supervisor_node (LLM Router)')
    pdf.body(
        'Uses Gemini 2.0 Flash to classify query intent: pipeline_health_node (stuck ROs, health, '
        'anomalies) or market_analytics_node (SCS_PERCENT, root cause, web search). Keyword-based '
        'fallback ensures routing resilience under API quota limits.'
    )
    pdf.sub('Nodes 3 & 4 -- Specialist Agents')
    pdf.body(
        'Each specialist follows: (1) Data retrieval from DuckDB by intent keyword, '
        '(2) Memory context injection into LLM prompt, (3) Gemini summarization -- never returning raw JSON.'
    )
    pdf.sub('Node 5 -- memory_writer_node')
    pdf.body(
        'After every turn: log_episodic_event() -> SQLite + ChromaDB; log_interaction() -> SQLite. '
        'Ensures every agent turn is permanently recorded for future session retrieval.'
    )
    pdf.sub('RosterIQState (TypedDict)')
    pdf.code(
        'messages: list          # conversation history\n'
        'session_id: str         # for episodic memory retrieval\n'
        'active_agent: str       # routing decision from supervisor node\n'
        'memory_context: dict    # {episodic, semantic, procedures, alerts}\n'
        'tool_outputs: list      # raw data from DuckDB tools\n'
        'final_answer: str       # LLM-synthesized natural language response\n'
        'procedure_context: str  # which procedure was run, if any'
    )

    # ── PAGE 6: DATA LAYER ─────────────────────────────────────────
    pdf.add_page()
    pdf.section('5', 'Data Layer & Tool Integration', GREEN)
    pdf.img(IMG_DATA_PIPELINE, 'Figure 3 -- Data Layer & Tool Integration Diagram')
    pdf.sub('5.1  DuckDB Analytics Engine (MetricsEngine)')
    pdf.table(
        ['Method', 'Derivation Logic'],
        [
            ['pipeline_health_score()', 'COUNT of Red flags per RO -> 0-7 composite score'],
            ['stage_delay_ratios()', 'actual_duration / AVG_duration per stage (schema.sql views)'],
            ['retry_overhead()', 'RUN_NO - 1 (extra processing attempts per RO)'],
            ['state_failure_rate()', 'IS_FAILED count / total ROs per CNT_STATE'],
            ['market_pipeline_correlation()', 'Cross-table JOIN: CSV1.CNT_STATE = CSV2.MARKET'],
            ['stuck_ros()', 'IS_STUCK = 1 with org, stage, and failure status'],
            ['get_market_trend_data(state)', 'Monthly SCS_PERCENT for a specific state market'],
        ],
        [80, 90],
    )
    pdf.body(
        'Thread Safety: threading.Lock() + per-query cursor isolation (self.con.cursor().execute()) '
        'prevents race conditions between Streamlit main thread and ProactiveMonitor background thread.'
    )
    pdf.sub('5.2  Tool Suite')
    pdf.table(
        ['Tool', 'File', 'Purpose'],
        [
            ['DataQueryTool', 'data_query.py', 'Health metrics, anomaly detection, cross-table joins'],
            ['RootCauseTracer', 'root_cause.py', 'Traces market failure -> org -> LOB -> SRC_SYS chain'],
            ['Visualizer', 'visualizer.py', '3 Plotly chart types: trend, stuck tracker, anomaly'],
            ['WebSearchTool', 'web_search.py', 'Tavily search: 4 domain templates + KB enrichment'],
            ['ReportGenerator', 'report_gen.py', 'Corporate PDF + Markdown pipeline health summary'],
        ],
        [40, 35, 95],
    )
    pdf.sub('5.3  Web Search Templates (Tavily)')
    pdf.table(
        ['Template', 'Targeted Query Pattern'],
        [
            ['complete_validation_failure', 'EDI 834 data processing {query} Complete Validation Failure AvailityPDM'],
            ['cms_rule_changes', 'CMS Medicaid recent rule changes provider directory accuracy in {query}'],
            ['lob_compliance', '{query} LOB healthcare data submission compliance standards'],
            ['provider_lookup', '{query} healthcare provider organization details locations'],
        ],
        [55, 115],
    )

    # ── PAGE 7: MEMORY ARCH OVERVIEW ───────────────────────────────
    pdf.add_page()
    pdf.section('6', 'Memory Architecture -- Deep Dive', PURPLE)
    pdf.body(
        'The memory architecture is the centerpiece of RosterIQ. All three memory types are persistent '
        'across sessions, independently demonstrable, and injected simultaneously on every agent turn '
        'via memory_loader_node. Web search results also enrich the Semantic KB at runtime.'
    )
    pdf.img(IMG_MEMORY_ARCH, 'Figure 4 -- Three-Layer Memory Architecture (Episodic / Procedural / Semantic)')

    # ── PAGE 8: EPISODIC MEMORY ────────────────────────────────────
    pdf.add_page()
    pdf.section('6.1', 'Episodic Memory', PURPLE)
    pdf.body('Design Philosophy: "What has this agent investigated before?"')
    pdf.ln(2)
    pdf.sub('Dual-Store Pattern')
    pdf.table(
        ['Store', 'Technology', 'Purpose'],
        [
            ['Structured', 'SQLite (roster_iq_memory.db)', 'Session-scoped exact retrieval, KPI snapshots'],
            ['Vector', 'ChromaDB (episodic_memory)', 'Cross-session semantic history search'],
            ['Checkpoints', 'SQLite (roster_iq_threads.db)', 'LangGraph full graph state persistence'],
        ],
        [30, 68, 72],
    )
    pdf.sub('SQLite Schema (3 Tables)')
    pdf.code(
        'interactions table:   session_id | timestamp | user_query | agent_response\n'
        'episodic_events:      session_id | query_intent | key_findings | kpi_snapshot(JSON)\n'
        '                      | severity | resolved | timestamp\n'
        'data_snapshots:       snapshot_type | snapshot_data(JSON) | timestamp'
    )
    pdf.sub('State Change Detection (ChangeDetector)')
    pdf.body(
        'Compares current operational state against the last saved snapshot on every session load, '
        'surfacing meaningful deltas in the Streamlit sidebar automatically:'
    )
    pdf.code(
        'def detect_all_changes(self) -> dict:\n'
        '    return {\n'
        '        "resolutions":   _detect_resolutions(),   # Was stuck -> now cleared\n'
        '        "new_anomalies": _detect_new_anomalies(),  # Newly stuck since last session\n'
        '        "kpi_drift":     _detect_kpi_drift()       # SCS_PERCENT delta >= 1.0%\n'
        '    }'
    )
    pdf.sub('Why Dual-Store?')
    pdf.bullet('SQLite: deterministic session-scoped retrieval -- "What did we do in SES-143522?"')
    pdf.bullet('ChromaDB: cross-session semantic retrieval -- "Have we seen this DART failure before?"')
    pdf.body(
        'Session snapshots are saved at the end of every Streamlit page load:\n'
        'save_data_snapshot("stuck_ro_ids", engine.get_stuck_ro_ids())\n'
        'save_data_snapshot("market_kpi_snapshot", engine.get_market_kpi_snapshot())'
    )

    # ── PAGE 9: PROCEDURAL MEMORY ──────────────────────────────────
    pdf.add_page()
    pdf.section('6.2', 'Procedural Memory', BLUE)
    pdf.body('Design Philosophy: "How does this agent know how to diagnose things?"')
    pdf.ln(2)
    pdf.sub('Two-Tier Registry')
    pdf.table(
        ['Store', 'Technology', 'Purpose'],
        [
            ['Procedure Registry', 'procedures.json (version-controlled JSON)', 'Human-readable, auditable definitions'],
            ['Vector Index', 'ChromaDB (procedure_registry)', 'Fuzzy natural language lookup'],
        ],
        [38, 68, 64],
    )
    pdf.sub('The 4 Named Diagnostic Procedures')
    pdf.table(
        ['Procedure', 'Key Parameters', 'Purpose'],
        [
            ['triage_stuck_ros', 'red_weight=3, yellow_weight=1, stuck_weight=2, top_k=10',
             'Ranks stuck ROs by composite escalation score'],
            ['market_health_report', 'scs_threshold=95.0, max_markets=10',
             'Correlates SCS_PERCENT with pipeline health flags'],
            ['retry_effectiveness_analysis', 'retry_lift_threshold=0.2, min_run_no=2',
             'Determines if retries recover or just add latency'],
            ['pipeline_bottleneck_scan', 'deviation_threshold=2.0, health_flag=Red',
             'Finds stages with duration > 2x historical average'],
        ],
        [52, 65, 53],
    )
    pdf.sub('Triage Escalation Score Formula')
    pdf.code(
        'score = (red_flags x 3) + (yellow_flags x 1) + (days_stuck x 2)\n'
        'ROs are ranked descending by this score for escalation priority.'
    )
    pdf.sub('Improvability -- Runtime Parameter Updates')
    pdf.body(
        'update_procedure_params(name, new_params) bumps the version number, updates the '
        'JSON file on disk, and re-syncs ChromaDB -- the procedure is permanently improved '
        'and survives app restarts. Users can refine procedure logic through natural language.'
    )
    pdf.sub('Why JSON + ChromaDB?')
    pdf.bullet('JSON: human-readable, git-trackable, auditable by ops teams in any text editor.')
    pdf.bullet('ChromaDB: fuzzy lookup -- find pipeline_bottleneck_scan using "scan for slow stages".')

    # ── PAGE 10: SEMANTIC MEMORY ───────────────────────────────────
    pdf.add_page()
    pdf.section('6.3', 'Semantic Memory', GREEN)
    pdf.body('Design Philosophy: "What does this agent know about the pipeline domain?"')
    pdf.ln(2)
    pdf.sub('Storage Architecture')
    pdf.table(
        ['Component', 'Detail'],
        [
            ['Vector Store', 'ChromaDB (semantic_knowledge collection, cosine similarity)'],
            ['Custom Embedder', 'SimpleHashEmbeddingFunction -- 256-dim MD5 hash, no model download'],
            ['Retrieval', 'Top-k cosine similarity, injected into every agent prompt via memory_loader'],
            ['Enrichment', 'Tavily search results -> add_knowledge() -> ChromaDB at runtime'],
        ],
        [38, 132],
    )
    pdf.sub('Custom Embedding -- SimpleHashEmbeddingFunction')
    pdf.code(
        'class SimpleHashEmbeddingFunction(EmbeddingFunction):\n'
        '    DIM = 256\n'
        '    def __call__(self, input: Documents) -> Embeddings:\n'
        '        for text in input:\n'
        '            vec = np.zeros(self.DIM, dtype=np.float32)\n'
        '            for word in str(text).lower().split():\n'
        '                idx = int(hashlib.md5(word.encode()).hexdigest(), 16) % self.DIM\n'
        '                vec[idx] += 1.0\n'
        '            vec /= np.linalg.norm(vec)  # L2 normalize'
    )
    pdf.body(
        'Rationale: SentenceTransformer requires ~400MB ONNX model. For a controlled healthcare '
        'vocabulary (known stage names, status codes, LOB abbreviations), keyword-level hash overlap '
        'is a strong retrieval signal. This eliminates the heavy dependency entirely.'
    )
    pdf.sub('Knowledge Base -- 10 Categories, 40+ Items')
    pdf.table(
        ['#', 'Category', 'Items', 'Example Concept'],
        [
            ['1', 'Pipeline Stages', '7', 'PRE_PROCESSING -> MAPPING -> ISF -> DART -> SPS_LOAD'],
            ['2', 'FILE_STATUS_CD Decoder', '5', '9=Stopped, 45=DART_REVIEW, 49=DART_GEN, 99=Resolved'],
            ['3', 'Health Flag Meanings', '4', 'Green/Yellow/Red thresholds and escalation actions'],
            ['4', 'Operational States', '5', 'IS_STUCK (recoverable) vs IS_FAILED (terminal, resubmit)'],
            ['5', 'Derived Metric Formulas', '5', 'Composite health score, Duration Deviation Ratio >3x'],
            ['6', 'Business Context', '5', 'LOB decoder (Medicare HMO, DSNP), SRC_SYS decoder'],
            ['7', 'KPI Thresholds', '3', 'SCS_PERCENT 95% threshold, retry lift rate 20% cutoff'],
            ['8', 'Compliance & External', '3', 'NCPDP, X12 834 EDI, CMS NPI quarterly updates'],
            ['9', 'Cross-CSV Reasoning', '2', 'CSV1 = leading indicator, CSV2 = lagging indicator'],
            ['10', 'Explainability Templates', '3', 'Structured response frameworks for anomaly explanations'],
        ],
        [8, 48, 14, 100],
    )
    pdf.sub('Web Search -> Semantic KB Enrichment Loop')
    pdf.body(
        'cms_rule_changes and complete_validation_failure search results are persisted to the '
        'semantic_knowledge ChromaDB collection via enrich_semantic_kb(). External regulatory '
        'discoveries from one session influence future analyses -- genuine self-improvement.'
    )

    # ── PAGE 11: INNOVATIONS ───────────────────────────────────────
    pdf.add_page()
    pdf.section('7', 'Innovations & Novel Design Patterns', ORANGE)

    innovations = [
        ('7.1  Memory-First Query Enrichment',
         'Before the LLM sees any query, memory_loader_node injects: episodic context (last N turns), '
         'semantic KB hits (top-3 domain facts), pipeline change summary, and live monitoring alerts. '
         'The model reasons from rich institutional context, fundamentally elevating response quality.'),
        ('7.2  Dual-Layer Episodic Store',
         'SQLite (indexed, session-scoped) + ChromaDB (cosine-search, cross-session) serve distinct '
         'needs. Neither technology alone would satisfy exact session replay AND cross-session semantic search.'),
        ('7.3  ChangeDetector as Proactive Episodic Reasoning',
         'Automated session-to-session state diffing surfaces operational changes without user prompting, '
         'directly implementing the "detect state changes on return" requirement.'),
        ('7.4  Web Search -> Semantic KB Closed Loop',
         'Tavily search results are persisted to ChromaDB (enrich_semantic_kb()), creating a self-improving '
         'knowledge base where external regulatory discoveries enrich future reasoning.'),
        ('7.5  LLM Router with Keyword Fallback Cascade',
         'Primary LLM-based routing with keyword-matching fallback ensures the agent remains functional '
         'even under Gemini free-tier 429 rate limits -- a critical production resilience pattern.'),
        ('7.6  SimpleHashEmbeddingFunction',
         'A custom 256-dim MD5 hash-based embedding eliminates the ~400MB SentenceTransformer ONNX model '
         'while maintaining adequate recall for the controlled healthcare terminology domain.'),
        ('7.7  Thread-Safe DuckDB',
         'threading.Lock() + per-query cursor isolation resolves the concurrent access crash between '
         'Streamlits main thread and the ProactiveMonitor background thread.'),
        ('7.8  Smart Pre-Agent Routing in Streamlit',
         'Pattern-matching in app.py routes common visualization queries to instant responses before '
         'invoking LangGraph, reducing LLM calls and latency for the most frequent query types.'),
    ]
    for title, desc in innovations:
        pdf.sub(title)
        pdf.body(desc)

    # ── PAGE 12: BONUS CHALLENGES ──────────────────────────────────
    pdf.add_page()
    pdf.section('8', 'Bonus Challenges Implemented', GREEN)

    pdf.sub('8.1  Proactive Monitoring [Implemented]')
    pdf.body(
        'ProactiveMonitor (src/agent/monitor.py) runs as a daemonized background thread, scanning both '
        'datasets without user prompting. Detects new stuck ROs (IS_STUCK=1) and markets trending below '
        '95% SCS_PERCENT. Writes to in-memory SQLite alert store with High/Medium severity. Alerts '
        'surface in Streamlit sidebar under "Live Alerts (Autonomous)" with gradient highlight cards. '
        'run_immediate_scan() populates alerts instantly on app startup.'
    )
    pdf.sub('8.2  Multi-Agent Architecture [Implemented]')
    pdf.body(
        'Supervisor -> [Pipeline Agent | Market Agent] implements true multi-agent delegation via LangGraph. '
        'Supervisor uses LLM intent classification; each specialist has its own data retrieval logic, '
        'tool use, and prompt engineering; both read shared memory_context; results funnel through a '
        'shared memory_writer node for consistent episodic persistence.'
    )
    pdf.sub('8.3  Root Cause Chaining [Implemented]')
    pdf.body(
        'RootCauseTracer (src/tools/root_cause.py) automatically traces a markets low SCS_PERCENT back '
        'through pipeline stages to specific organizations, source systems, and lines of business:'
    )
    pdf.code(
        'Market SCS_PERCENT Drop\n'
        '  -> CSV1 cross-table join -> Failed RO count per org per state\n'
        '  -> Identify dominant LOB + SRC_SYS with highest Red flags\n'
        '  -> Match FAILURE_STATUS patterns (Complete Validation Failure, Schema mismatch)\n'
        '  -> Generate narrative with evidence from both CSVs'
    )

    # ── PAGE 13: CHALLENGES ─────────────────────────────────────────
    pdf.add_page()
    pdf.section('9', 'Challenges & Learnings', ORANGE)

    challenges = [
        ('9.1  DuckDB Thread Safety -- Unexpected Crash',
         'Problem: INTERNAL Error: Attempted to dereference unique_ptr that is NULL! under concurrent '
         'DuckDB access from Streamlits main thread and ProactiveMonitor.\n'
         'Root Cause: DuckDB in-memory connection is not thread-safe for concurrent execute() calls.\n'
         'Solution: threading.Lock() + per-query cursor isolation via self.con.cursor().execute(sql).\n'
         'Learning: Design for concurrency from day one when background threads share state with web frameworks.'),
        ('9.2  ChromaDB Embedding Function Conflict',
         'Problem: Switching from SentenceTransformer to SimpleHashEmbeddingFunction caused "ValueError: '
         'Embedding function mismatch" for existing on-disk ChromaDB collections.\n'
         'Root Cause: ChromaDB stores a fingerprint of the embedding function with the collection.\n'
         'Solution: Conflict recovery pattern -- catch ValueError, delete stale collection, recreate.\n'
         'Learning: Embedding function changes are breaking changes. Build recovery paths from day one.'),
        ('9.3  LLM Quota Exhaustion (429 Errors)',
         'Problem: Free-tier Gemini imposes per-minute limits. Supervisor + specialist each making LLM '
         'calls = quota exhausted during intensive 36-hour testing.\n'
         'Solution: max_retries=6, timeout=60 in ChatGoogleGenerativeAI; specific 429/ResourceExhausted '
         'detection; keyword fallback in supervisor; smart pre-agent routing to reduce LLM calls.\n'
         'Learning: Multi-agent systems multiply LLM usage. Always design non-LLM fallback paths.'),
        ('9.4  fpdf API Versioning',
         'Problem: PDF generator failed with TypeError -- output() API differs between fpdf versions.\n'
         'Solution: result.encode("latin-1") if isinstance(result, str) else result.\n'
         'Learning: Pin library versions in requirements.txt. Test output functions explicitly.'),
    ]
    for title, desc in challenges:
        pdf.sub(title)
        pdf.body(desc)
        pdf.ln(1)

    pdf.sub('What We Would Do Differently')
    for item in [
        'Fully implement procedure execution SQL (triage, bottleneck scan) -- registry and routing work, '
        'but deep SQL execution was partially stubbed due to 36-hour time constraint.',
        'Use LangGraph .astream() with async for real-time token streaming instead of blocking .invoke().',
        'Replace blocking time.sleep() in ProactiveMonitor with asyncio.sleep().',
        'Implement automated feedback loop where LLM extracts parameter refinements from user corrections.',
        'Add retry strategy comparison chart: retry success rates by LOB and SRC_SYS per state.',
    ]:
        pdf.bullet(item)

    # ── PAGE 14: TECH STACK ─────────────────────────────────────────
    pdf.add_page()
    pdf.section('10', 'Appendix: Technology Stack & Directory Structure')
    pdf.table(
        ['Component', 'Technology / Library', 'Purpose'],
        [
            ['Agent Framework', 'LangGraph 0.2.x', 'Multi-agent state graph with SQLite checkpointing'],
            ['LLM', 'Google Gemini 2.0 Flash', 'Supervisor routing + natural language summarization'],
            ['Vector Database', 'ChromaDB (3 collections)', 'Semantic + Episodic + Procedural memory'],
            ['Structured DB', 'SQLite', 'Episodic interaction log + KPI snapshots'],
            ['Analytics Engine', 'DuckDB (in-memory)', 'SQL views over provider roster CSV files'],
            ['Web Framework', 'Streamlit', 'Chat UI + visualizations + sidebar + session mgmt'],
            ['Charting', 'Plotly', 'Interactive pipeline health and market trend charts'],
            ['PDF Generation', 'fpdf2', 'Corporate pipeline health PDF report'],
            ['Web Search', 'Tavily API', 'External healthcare regulatory context retrieval'],
            ['Data Processing', 'Pandas', 'DataFrame operations and transformations'],
            ['Env Management', 'python-dotenv', 'API key management via .env file'],
        ],
        [38, 55, 77],
    )
    pdf.sub('Project Directory Structure')
    pdf.code(
        'Healthcare-roster-agent/\n'
        'app.py                         # Streamlit application (Presentation Layer)\n'
        'src/\n'
        '  agent/\n'
        '    graph.py                   # LangGraph 5-node StateGraph assembly\n'
        '    nodes.py                   # memory_loader, supervisor, pipeline_agent,\n'
        '                               #   market_agent, memory_writer\n'
        '    monitor.py                 # ProactiveMonitor background thread\n'
        '    state.py                   # RosterIQState TypedDict definition\n'
        '  db/\n'
        '    duckdb_engine.py           # MetricsEngine: 7 derived metrics + thread safety\n'
        '    schema.sql                 # composite_health_view, duration_deviation_view\n'
        '  memory/\n'
        '    episodic.py               # SQLite + ChromaDB dual-store episodic memory\n'
        '    procedural.py             # JSON + ChromaDB procedure registry (4 procedures)\n'
        '    semantic.py               # ChromaDB domain KB: 40+ items, 10 categories\n'
        '    procedures.json           # Versioned diagnostic procedure definitions\n'
        '    change_detector.py        # Session-to-session state differencing\n'
        '  tools/\n'
        '    data_query.py             # DataQueryTool: health, anomaly, cross-join\n'
        '    report_gen.py             # PDF + Markdown pipeline health report\n'
        '    root_cause.py             # RootCauseTracer: causal chain analysis\n'
        '    visualizer.py             # Plotly suite: trend, stuck, anomaly charts\n'
        '    web_search.py             # Tavily: 4 templates + KB enrichment\n'
        'data/\n'
        '  roster_processing_details.csv        # CSV 1: File-level pipeline data\n'
        '  aggregated_operational_metrics.csv   # CSV 2: Market-level transaction data\n'
        'chroma_db/                             # Persistent ChromaDB (3 collections)\n'
        'roster_iq_memory.db                    # SQLite episodic store\n'
        'roster_iq_threads.db                   # LangGraph SqliteSaver checkpoints'
    )


    pdf.output(OUTPUT_PATH)
    sz = os.path.getsize(OUTPUT_PATH) / 1024
    print(f'PDF generated: {OUTPUT_PATH}')
    print(f'Pages: {pdf.page_no()}  |  Size: {sz:.0f} KB')


if __name__ == '__main__':
    build()
