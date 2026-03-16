import json
import anthropic
from http.server import BaseHTTPRequestHandler

ATRIUM_CONSTRUCTION_CONTEXT = """
Company: Atrium Construction Corp
Week: March 10–14, 2026

Active Projects:
- Riverside Office Tower (Phase 2): Steel framing 78% complete, on schedule
- Greenfield Residential Complex: Foundation poured, awaiting inspection
- Downtown Renovation (Block 5): Interior fit-out in progress, minor delay due to material delivery

Team Updates:
- 42 workers on-site across all projects
- 2 new safety certifications completed
- Equipment: 3 cranes operational, 1 scheduled for maintenance Friday

Budget Summary:
- Riverside Tower: $2.1M spent of $2.4M quarterly budget
- Greenfield: $890K spent of $1.2M budget
- Downtown Block 5: $450K spent of $500K budget

Issues & Risks:
- Steel delivery for Riverside Tower delayed by 3 days (vendor supply chain issue)
- Rain forecast for Thursday may impact Greenfield exterior work
- Downtown Block 5 permit renewal due next week

Milestones This Week:
- Completed concrete pour for Greenfield west wing
- Passed electrical rough-in inspection for Downtown Block 5
"""


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        client = anthropic.Anthropic()

        prompt = f"""You are a professional construction project manager.
Based on the following project data, generate a concise and professional
weekly status report for Atrium Construction Corp.

The report should include:
1. Executive Summary
2. Project Status Overview (per project)
3. Key Accomplishments
4. Issues & Risks
5. Next Week's Priorities

Project Data:
{ATRIUM_CONSTRUCTION_CONTEXT}

Write the report in a clear, professional format suitable for senior management.
Use markdown formatting for headers and lists.
"""

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )

        report = response.content[0].text

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"report": report}).encode())
