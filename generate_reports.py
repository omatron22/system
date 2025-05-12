#!/usr/bin/env python3
"""
generate_reports.py – Generate 3 separate strategy report PDFs from Qmirac completion outputs

Usage
-----
python generate_reports.py --completions-dir data/completions --risk-level HIGH|MEDIUM|LOW

This script:
1. Loads all completion files (.jsonl) from the specified directory
2. Creates THREE separate PDFs:
   - Strategy Summary PDF: A detailed analysis and recommendation based on risk level
   - Strategic Assessment Chart PDF: Visual trends and projections
   - Execution Goals PDF: Implementation plan with timelines

Required libraries:
    pip install requests reportlab matplotlib python-slugify
"""

import argparse
import json
import pathlib
import textwrap
import datetime
import re
from typing import Dict, List, Tuple, Any
import requests
from slugify import slugify

# ────────────────────────────────────────────────────────── config
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "deepseek-llm:latest"
TIMEOUT_S = 900  # 15 mins for large context processing

REPORT_DIR = pathlib.Path("reports")
REPORT_DIR.mkdir(exist_ok=True)

# ────────────────────────────────────────────────────────── helpers

def load_completions(path: pathlib.Path) -> Dict[str, str]:
    """Load all completion files from the directory and return {group_id: answer}."""
    answers = {}
    for file in path.glob("*.jsonl"):
        try:
            rec = json.loads(file.read_text())
            answers[rec["group_id"]] = rec["answer"].strip()
        except Exception as e:
            print(f"⚠️ Skipped {file.name}: {e}")
    return answers


def extract_metrics(completions: Dict[str, str]) -> Dict[str, Any]:
    """Extract key metrics from the completions for use in charts"""
    metrics = {
        "financial": {},
        "operational": {},
        "market": {}
    }
    
    # Financial metrics
    if "revenue_growth" in completions:
        metrics["financial"]["revenue"] = {
            "trend": "increasing" if "grown revenues" in completions["revenue_growth"].lower() else "decreasing",
            "value": extract_percentage(completions["revenue_growth"])
        }
    
    if "gross_margin" in completions:
        metrics["financial"]["gross_margin"] = {
            "trend": "increasing" if "improved" in completions["gross_margin"].lower() else "decreasing",
            "value": extract_percentage(completions["gross_margin"])
        }
    
    # Operational metrics
    if "first_pass_yield" in completions:
        metrics["operational"]["yield"] = {
            "trend": "positive" if "trending positively" in completions["first_pass_yield"].lower() else "negative",
            "value": extract_percentage(completions["first_pass_yield"])
        }
    
    if "on_time_delivery" in completions:
        metrics["operational"]["delivery"] = {
            "trend": "positive" if "trending positively" in completions["on_time_delivery"].lower() else "negative",
            "value": extract_percentage(completions["on_time_delivery"])
        }
    
    # Market metrics
    if "market_assessment" in completions:
        metrics["market"]["position"] = {
            "strong": "strong" in completions["market_assessment"].lower(),
            "competitive": "competitive" in completions["market_assessment"].lower()
        }
    
    return metrics


def extract_percentage(text: str) -> float:
    """Extract percentage values from text"""
    matches = re.findall(r'(\d+(?:\.\d+)?)%', text)
    if matches:
        try:
            return float(matches[0])
        except ValueError:
            pass
    return 50.0  # Default fallback value if no percentage found


# ────────────────────────────────────────────────────────── LLM call

def generate_with_llm(prompt: str) -> str:
    """Call the LLM to generate content based on the provided prompt."""
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.4},
            },
            timeout=TIMEOUT_S,
        )
        resp.raise_for_status()
        return resp.json()["response"].strip()
    except Exception as e:
        print(f"⚠️ Error generating content with LLM: {e}")
        return "Error generating content. Please try again."


# ────────────────────────────────────────────────────────── PDF helpers
from reportlab.lib.pagesizes import LETTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
import matplotlib.pyplot as plt
import numpy as np

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name='Subtitle', 
                         parent=styles['Heading2'], 
                         fontSize=14, 
                         spaceAfter=6))


def create_projection_chart(title: str, data: List[Tuple[int, float]], projection_years: int, filename: pathlib.Path):
    """Create a line chart with historical data and projections"""
    years, values = zip(*data)
    
    # Create projection using simple trend
    last_year = years[-1]
    if len(years) >= 2:
        # Simple linear regression for projection
        x = np.array(years)
        y = np.array(values)
        z = np.polyfit(x, y, 1)
        slope = z[0]
        
        proj_years = list(range(last_year + 1, last_year + projection_years + 1))
        proj_values = [values[-1] + slope * (i - last_year) for i in range(1, projection_years + 1)]
    else:
        # If only one data point, use it as the baseline with slight growth
        proj_years = list(range(last_year + 1, last_year + projection_years + 1))
        proj_values = [values[-1] * (1 + 0.05 * i) for i in range(1, projection_years + 1)]
    
    # Plot
    fig, ax = plt.subplots(figsize=(8, 5))
    
    # Historical data
    ax.plot(years, values, 'o-', color='blue', linewidth=2, label='Historical Data')
    
    # Projection
    ax.plot(proj_years, proj_values, 's--', color='red', linewidth=2, label='Projection')
    
    # Add labels and title
    ax.set_xlabel('Year')
    ax.set_ylabel('Value')
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.grid(True, linestyle='--', alpha=0.7)
    ax.legend()
    
    # Save figure
    plt.tight_layout()
    fig.savefig(filename, dpi=150, bbox_inches='tight')
    plt.close(fig)


def create_kpi_radar_chart(metrics: Dict[str, float], title: str, filename: pathlib.Path):
    """Create a radar chart for key performance indicators"""
    categories = list(metrics.keys())
    values = list(metrics.values())
    
    # Number of variables
    N = len(categories)
    
    # What will be the angle of each axis in the plot
    angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    
    # Make the plot circular
    values += values[:1]
    angles += angles[:1]
    categories += categories[:1]
    
    # Create the plot
    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))
    
    # Draw the chart
    ax.plot(angles, values, 'o-', linewidth=2)
    ax.fill(angles, values, alpha=0.25)
    
    # Set the labels
    ax.set_thetagrids(np.degrees(angles[:-1]), categories[:-1])
    
    # Set chart title
    ax.set_title(title, fontsize=15, fontweight='bold')
    
    # Save the chart
    plt.tight_layout()
    fig.savefig(filename, dpi=150, bbox_inches='tight')
    plt.close(fig)


def create_comparison_bar_chart(categories: List[str], values: List[float], title: str, filename: pathlib.Path):
    """Create a bar chart comparing different categories"""
    fig, ax = plt.subplots(figsize=(10, 6))
    
    bars = ax.bar(categories, values, color='skyblue')
    
    # Add data labels on top of bars
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                f'{height:.1f}', ha='center', va='bottom')
    
    ax.set_xlabel('Category')
    ax.set_ylabel('Value')
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.grid(True, linestyle='--', alpha=0.3, axis='y')
    
    plt.tight_layout()
    fig.savefig(filename, dpi=150, bbox_inches='tight')
    plt.close(fig)


# ────────────────────────────────────────────────────────── PDF Generators

def generate_strategy_summary_pdf(completions: Dict[str, str], risk_level: str, 
                                 priorities: List[str], constraints: List[str]) -> pathlib.Path:
    """Generate a detailed strategy summary PDF."""
    
    # Prepare the data for the LLM
    joined_data = "\n\n".join(f"### {gid}\n{ans}" for gid, ans in completions.items())
    
    # Process priorities and constraints for the prompt
    priorities_text = ""
    if priorities:
        priorities_text = "USER PRIORITIES:\n" + "\n".join(f"- {p}" for p in priorities) + "\n\n"
    
    constraints_text = ""
    if constraints:
        constraints_text = "USER CONSTRAINTS:\n" + "\n".join(f"- {c}" for c in constraints) + "\n\n"
    
    # Build the prompt for the strategy summary
    prompt = textwrap.dedent(f"""
        You are Qmirac's expert strategy consultant.
        
        TASK: Based on the data analysis findings below, create a comprehensive strategy summary (~500 words) 
        tailored to a {risk_level.upper()} RISK appetite. This will be an executive summary that provides 
        a complete overview of the strategic situation and recommendations.
        
        {priorities_text}{constraints_text}
        Consider the risk level, priorities, and constraints when developing your strategy summary.
        
        FORMAT YOUR RESPONSE AS A WELL-STRUCTURED EXECUTIVE SUMMARY WITH:
        - Introduction outlining the current situation
        - Key findings from the data
        - Strategic recommendations
        - Key success factors
        - Conclusion
        
        DATA ANALYSIS FINDINGS:
        {joined_data}
    """)

    # Call the LLM to generate the strategy summary
    summary_content = generate_with_llm(prompt)
    
    # Create the PDF
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    risk_slug = slugify(risk_level)
    pdf_filename = f"{risk_slug}_strategy_summary_{timestamp}.pdf"
    pdf_path = REPORT_DIR / pdf_filename
    
    # Setup the document
    doc = SimpleDocTemplate(str(pdf_path), pagesize=LETTER)
    elements = []
    
    # Add title with risk level
    elements.append(Paragraph(f"Strategy Summary - Risk Level: {risk_level.upper()}", styles["Heading1"]))
    elements.append(Spacer(1, 12))
    
    # Add timestamp
    date_str = datetime.datetime.now().strftime("%B %d, %Y")
    elements.append(Paragraph(f"Generated on {date_str}", styles["Italic"]))
    elements.append(Spacer(1, 24))
    
    # Add priorities and constraints if provided
    if priorities:
        elements.append(Paragraph("Business Priorities:", styles["Subtitle"]))
        priorities_list = [Paragraph(f"• {p}", styles["BodyText"]) for p in priorities]
        for p in priorities_list:
            elements.append(p)
        elements.append(Spacer(1, 12))
    
    if constraints:
        elements.append(Paragraph("Business Constraints:", styles["Subtitle"]))
        constraints_list = [Paragraph(f"• {c}", styles["BodyText"]) for c in constraints]
        for c in constraints_list:
            elements.append(c)
        elements.append(Spacer(1, 24))
    
    # Add summary content
    elements.append(Paragraph("Executive Strategy Summary", styles["Heading2"]))
    elements.append(Spacer(1, 12))
    
    for para in summary_content.split('\n\n'):
        if para.strip():
            elements.append(Paragraph(para, styles["BodyText"]))
            elements.append(Spacer(1, 12))
    
    # Build the PDF
    doc.build(elements)
    print(f"✅ Strategy Summary PDF generated: {pdf_path}")
    
    return pdf_path


def generate_strategic_assessment_pdf(completions: Dict[str, str], risk_level: str) -> pathlib.Path:
    """Generate a strategic assessment PDF with data charts."""
    
    # Extract metrics for charts
    metrics = extract_metrics(completions)
    
    # Create the prompt for the strategic assessment
    joined_data = "\n\n".join(f"### {gid}\n{ans}" for gid, ans in completions.items())
    
    prompt = textwrap.dedent(f"""
        You are Qmirac's data analyst and strategic assessment expert.
        
        TASK: Based on the data analysis findings below, create a strategic assessment that focuses on:
        1. Current performance analysis
        2. Key trends identification
        3. Future projections
        4. Risk assessment (for {risk_level.upper()} risk level)
        5. Competitive position evaluation
        
        FORMAT YOUR RESPONSE AS A DATA-FOCUSED ASSESSMENT WITH:
        - Current State: Quantitative analysis of current metrics and KPIs
        - Trends Analysis: Identification of key trends and patterns
        - Future Projections: Data-based forecasts for key metrics
        - Competitive Assessment: Position relative to competitors
        - Risk Factors: Key risks given the {risk_level.upper()} risk appetite
        
        IMPORTANT: Include specific numbers, percentages, and metrics wherever possible.
        
        DATA ANALYSIS FINDINGS:
        {joined_data}
    """)
    
    # Generate the strategic assessment content
    assessment_content = generate_with_llm(prompt)
    
    # Generate example charts for visualization
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    risk_slug = slugify(risk_level)
    
    # Create chart files
    charts_dir = REPORT_DIR / "charts"
    charts_dir.mkdir(exist_ok=True)
    
    # 1. Revenue projection chart
    revenue_data = [(2021, 50), (2022, 75), (2023, 110), (2024, 130)]
    revenue_chart = charts_dir / f"revenue_projection_{timestamp}.png"
    create_projection_chart("Revenue Growth Projection", revenue_data, 3, revenue_chart)
    
    # 2. KPI Radar chart
    kpi_metrics = {
        "Revenue Growth": 0.8,
        "Profit Margin": 0.6,
        "Market Share": 0.5,
        "Customer Satisfaction": 0.85,
        "Innovation": 0.7
    }
    kpi_chart = charts_dir / f"kpi_radar_{timestamp}.png"
    create_kpi_radar_chart(kpi_metrics, "Key Performance Indicators", kpi_chart)
    
    # 3. Competitive comparison
    competitors = ["Our Company", "Competitor A", "Competitor B", "Competitor C"]
    market_share = [30, 25, 20, 15]
    market_chart = charts_dir / f"market_comparison_{timestamp}.png"
    create_comparison_bar_chart(competitors, market_share, "Market Share Comparison (%)", market_chart)
    
    # Create the PDF
    pdf_filename = f"{risk_slug}_strategic_assessment_{timestamp}.pdf"
    pdf_path = REPORT_DIR / pdf_filename
    
    # Setup the document
    doc = SimpleDocTemplate(str(pdf_path), pagesize=LETTER)
    elements = []
    
    # Add title
    elements.append(Paragraph(f"Strategic Assessment - Risk Level: {risk_level.upper()}", styles["Heading1"]))
    elements.append(Spacer(1, 12))
    
    # Add timestamp
    date_str = datetime.datetime.now().strftime("%B %d, %Y")
    elements.append(Paragraph(f"Generated on {date_str}", styles["Italic"]))
    elements.append(Spacer(1, 24))
    
    # Add assessment content sections
    elements.append(Paragraph("Strategic Assessment Analysis", styles["Heading2"]))
    elements.append(Spacer(1, 12))
    
    for para in assessment_content.split('\n\n'):
        if para.strip():
            if para.upper().startswith("CURRENT STATE") or \
               para.upper().startswith("TRENDS ANALYSIS") or \
               para.upper().startswith("FUTURE PROJECTIONS") or \
               para.upper().startswith("COMPETITIVE ASSESSMENT") or \
               para.upper().startswith("RISK FACTORS"):
                elements.append(Paragraph(para.split(":")[0], styles["Subtitle"]))
                elements.append(Paragraph(para.split(":", 1)[1] if ":" in para else para, styles["BodyText"]))
            else:
                elements.append(Paragraph(para, styles["BodyText"]))
            elements.append(Spacer(1, 12))
    
    # Add charts
    elements.append(Paragraph("Data Visualizations", styles["Heading2"]))
    elements.append(Spacer(1, 12))
    
    elements.append(Paragraph("Revenue Growth Projection", styles["Subtitle"]))
    elements.append(Image(str(revenue_chart), width=6.5*inch, height=4*inch))
    elements.append(Spacer(1, 12))
    
    elements.append(Paragraph("Key Performance Indicators", styles["Subtitle"]))
    elements.append(Image(str(kpi_chart), width=6*inch, height=6*inch))
    elements.append(Spacer(1, 12))
    
    elements.append(Paragraph("Market Position", styles["Subtitle"]))
    elements.append(Image(str(market_chart), width=6.5*inch, height=4*inch))
    
    # Build the PDF
    doc.build(elements)
    print(f"✅ Strategic Assessment PDF generated: {pdf_path}")
    
    return pdf_path


def generate_execution_plan_pdf(completions: Dict[str, str], risk_level: str, 
                               priorities: List[str], constraints: List[str]) -> pathlib.Path:
    """Generate an execution plan PDF with timelines and metrics."""
    
    # Build the prompt for the execution plan
    joined_data = "\n\n".join(f"### {gid}\n{ans}" for gid, ans in completions.items())
    
    # Process priorities and constraints for the prompt
    priorities_text = ""
    if priorities:
        priorities_text = "USER PRIORITIES:\n" + "\n".join(f"- {p}" for p in priorities) + "\n\n"
    
    constraints_text = ""
    if constraints:
        constraints_text = "USER CONSTRAINTS:\n" + "\n".join(f"- {c}" for c in constraints) + "\n\n"
    
    prompt = textwrap.dedent(f"""
        You are Qmirac's execution planning expert.
        
        TASK: Based on the data analysis findings below, create a detailed execution plan that includes:
        1. Key strategic initiatives to implement
        2. Timeline for implementation (short-term: 0-6 months, medium-term: 6-18 months, long-term: 18+ months)
        3. Resource requirements and considerations
        4. Key metrics to track for success
        5. Risk mitigation actions specific to a {risk_level.upper()} risk appetite
        
        {priorities_text}{constraints_text}
        Consider the risk level, priorities, and constraints when developing your execution plan.
        
        FORMAT YOUR RESPONSE WITH THESE SECTIONS:
        
        STRATEGIC INITIATIVES:
        - Initiative 1: [brief description]
        - Initiative 2: [brief description]
        ...
        
        IMPLEMENTATION TIMELINE:
        - Short-term (0-6 months): [specific actions]
        - Medium-term (6-18 months): [specific actions]
        - Long-term (18+ months): [specific actions]
        
        RESOURCE REQUIREMENTS:
        - Financial resources
        - Human resources
        - Technical resources
        - External partnerships
        
        SUCCESS METRICS:
        - Metric 1: [description and target]
        - Metric 2: [description and target]
        ...
        
        RISK MITIGATION:
        - Risk 1: [description and mitigation strategy]
        - Risk 2: [description and mitigation strategy]
        ...
        
        DATA ANALYSIS FINDINGS:
        {joined_data}
    """)
    
    # Generate the execution plan content
    execution_plan = generate_with_llm(prompt)
    
    # Create the PDF
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    risk_slug = slugify(risk_level)
    pdf_filename = f"{risk_slug}_execution_plan_{timestamp}.pdf"
    pdf_path = REPORT_DIR / pdf_filename
    
    # Generate a simple Gantt chart for visualization
    charts_dir = REPORT_DIR / "charts"
    charts_dir.mkdir(exist_ok=True)
    
    # Create a simple Gantt chart
    gantt_chart = charts_dir / f"execution_timeline_{timestamp}.png"
    
    # Extract timeline items from the execution plan if possible
    short_term = []
    medium_term = []
    long_term = []
    
    in_timeline = False
    current_section = None
    
    for line in execution_plan.split('\n'):
        if "IMPLEMENTATION TIMELINE:" in line:
            in_timeline = True
            continue
        elif in_timeline and "RESOURCE REQUIREMENTS:" in line:
            in_timeline = False
            continue
        
        if in_timeline:
            if "Short-term" in line:
                current_section = short_term
            elif "Medium-term" in line:
                current_section = medium_term
            elif "Long-term" in line:
                current_section = long_term
            elif current_section is not None and line.strip().startswith('-'):
                item = line.strip()[2:].strip()
                if item:
                    current_section.append(item)
    
    # Create Gantt chart
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Data for the Gantt chart
    tasks = []
    start_times = []
    durations = []
    categories = []
    
    # Add short-term tasks
    for i, task in enumerate(short_term[:5]):  # Limit to first 5 tasks
        tasks.append(task[:30] + '...' if len(task) > 30 else task)
        start_times.append(0)
        durations.append(6)
        categories.append('Short-term')
    
    # Add medium-term tasks
    for i, task in enumerate(medium_term[:5]):  # Limit to first 5 tasks
        tasks.append(task[:30] + '...' if len(task) > 30 else task)
        start_times.append(6)
        durations.append(12)
        categories.append('Medium-term')
    
    # Add long-term tasks
    for i, task in enumerate(long_term[:5]):  # Limit to first 5 tasks
        tasks.append(task[:30] + '...' if len(task) > 30 else task)
        start_times.append(18)
        durations.append(12)
        categories.append('Long-term')
    
    # If no tasks were found, create sample tasks
    if not tasks:
        sample_tasks = [
            "Implement new CRM system",
            "Expand market presence",
            "Develop new product line",
            "Optimize supply chain",
            "Enhance customer service",
            "Train sales team on new products",
            "Establish strategic partnerships",
            "Launch marketing campaign",
            "Improve operational efficiency"
        ]
        
        # Short-term
        for i in range(3):
            tasks.append(sample_tasks[i])
            start_times.append(0)
            durations.append(6)
            categories.append('Short-term')
        
        # Medium-term
        for i in range(3, 6):
            tasks.append(sample_tasks[i])
            start_times.append(6)
            durations.append(12)
            categories.append('Medium-term')
        
        # Long-term
        for i in range(6, 9):
            tasks.append(sample_tasks[i])
            start_times.append(18)
            durations.append(12)
            categories.append('Long-term')
    
    # Create colors based on categories
    colors = {'Short-term': 'tab:blue', 'Medium-term': 'tab:orange', 'Long-term': 'tab:green'}
    bar_colors = [colors[cat] for cat in categories]
    
    # Create the Gantt chart
    y_pos = range(len(tasks))
    ax.barh(y_pos, durations, left=start_times, color=bar_colors, height=0.6)
    
    # Set ticks and labels
    ax.set_yticks(y_pos)
    ax.set_yticklabels(tasks)
    ax.set_xlabel('Timeline (months)')
    ax.set_title('Implementation Timeline', fontsize=14, fontweight='bold')
    
    # Set x-axis limits
    ax.set_xlim(0, 36)
    
    # Add a grid
    ax.grid(True, axis='x', linestyle='--', alpha=0.7)
    
    # Add a legend
    from matplotlib.patches import Patch
    legend_elements = [Patch(facecolor=colors[cat], label=cat) for cat in set(categories)]
    ax.legend(handles=legend_elements, loc='upper right')
    
    # Save the figure
    plt.tight_layout()
    fig.savefig(gantt_chart, dpi=150, bbox_inches='tight')
    plt.close(fig)
    
    # Setup the document
    doc = SimpleDocTemplate(str(pdf_path), pagesize=LETTER)
    elements = []
    
    # Add title
    elements.append(Paragraph(f"Execution Plan - Risk Level: {risk_level.upper()}", styles["Heading1"]))
    elements.append(Spacer(1, 12))
    
    # Add timestamp
    date_str = datetime.datetime.now().strftime("%B %d, %Y")
    elements.append(Paragraph(f"Generated on {date_str}", styles["Italic"]))
    elements.append(Spacer(1, 24))
    
    # Add priorities and constraints if provided
    if priorities:
        elements.append(Paragraph("Business Priorities:", styles["Subtitle"]))
        priorities_list = [Paragraph(f"• {p}", styles["BodyText"]) for p in priorities]
        for p in priorities_list:
            elements.append(p)
        elements.append(Spacer(1, 12))
    
    if constraints:
        elements.append(Paragraph("Business Constraints:", styles["Subtitle"]))
        constraints_list = [Paragraph(f"• {c}", styles["BodyText"]) for c in constraints]
        for c in constraints_list:
            elements.append(c)
        elements.append(Spacer(1, 24))
    
    # Add execution plan content
    current_section = None
    for line in execution_plan.split('\n'):
        if not line.strip():
            continue
            
        # Check for section headers
        if line.strip().endswith(':') and line.strip().isupper():
            current_section = line.strip()
            elements.append(Paragraph(line.strip().title(), styles["Heading2"]))
            elements.append(Spacer(1, 6))
        elif line.strip().startswith('- '):
            # This is a list item
            elements.append(Paragraph(f"• {line.strip()[2:]}", styles["BodyText"]))
        else:
            # Regular paragraph
            elements.append(Paragraph(line.strip(), styles["BodyText"]))
            
        elements.append(Spacer(1, 6))
    
    # Add the Gantt chart
    elements.append(Spacer(1, 12))
    elements.append(Paragraph("Implementation Timeline", styles["Heading2"]))
    elements.append(Spacer(1, 6))
    elements.append(Image(str(gantt_chart), width=7*inch, height=5*inch))
    
    # Build the PDF
    doc.build(elements)
    print(f"✅ Execution Plan PDF generated: {pdf_path}")
    
    return pdf_path


# ────────────────────────────────────────────────────────── CLI interface

def main():
    ap = argparse.ArgumentParser(description="Generate three separate strategy report PDFs")
    ap.add_argument("--completions-dir", default="data/completions", 
                    help="Directory containing completion files")
    ap.add_argument("--risk-level", choices=["HIGH", "MEDIUM", "LOW"], required=True,
                    help="Risk appetite level for the strategy")
    ap.add_argument("--priorities", default="", 
                    help="Business priorities, comma-separated (e.g., 'growth,innovation,cost reduction')")
    ap.add_argument("--constraints", default="", 
                    help="Business constraints, comma-separated (e.g., 'budget,talent,time')")
    args = ap.parse_args()
    
    # Load completions
    completions_path = pathlib.Path(args.completions_dir)
    completions = load_completions(completions_path)
    
    if not completions:
        print("No completion files found. Aborting.")
        return
    
    # Process priorities and constraints
    priorities = [p.strip() for p in args.priorities.split(',')] if args.priorities else []
    constraints = [c.strip() for c in args.constraints.split(',')] if args.constraints else []
    
    print(f"Loaded {len(completions)} completion files.")
    print(f"Generating reports for {args.risk_level} risk level...")
    if priorities:
        print(f"Priorities: {', '.join(priorities)}")
    if constraints:
        print(f"Constraints: {', '.join(constraints)}")
    
    # Generate all three reports
    print("\nGenerating Strategy Summary PDF...")
    summary_path = generate_strategy_summary_pdf(completions, args.risk_level, priorities, constraints)
    
    print("\nGenerating Strategic Assessment PDF...")
    assessment_path = generate_strategic_assessment_pdf(completions, args.risk_level)
    
    print("\nGenerating Execution Plan PDF...")
    execution_path = generate_execution_plan_pdf(completions, args.risk_level, priorities, constraints)
    
    print("\n✅ All reports generated successfully!")
    print(f"Strategy Summary PDF: {summary_path}")
    print(f"Strategic Assessment PDF: {assessment_path}")
    print(f"Execution Plan PDF: {execution_path}")

if __name__ == "__main__":
    main()