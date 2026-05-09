"""Build the synthetic contract fixtures used by Sprint 1 tests.

Renders three synthetic PDFs using ReportLab (pure Python, no system libs).
ReportLab is in the backend's `fixtures` dep group, NOT a runtime dep.
The PDFs themselves are committed; this script exists so any contributor
can regenerate them. Run from the repo root:

    uv sync --group fixtures           # one-time
    uv run python fixtures/build_fixtures.py

Each synthetic contract has DELIBERATE issues planted for the Caveat AI
analyzer to flag. Provenance and planted issues are documented in
fixtures/contracts/README.md.
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

OUT_DIR = Path(__file__).parent / "contracts"

# ---- Styles ----------------------------------------------------------------

_styles = getSampleStyleSheet()
TITLE = ParagraphStyle(
    "Title",
    parent=_styles["Title"],
    fontName="Times-Bold",
    fontSize=14,
    alignment=1,  # center
    spaceAfter=18,
    leading=18,
)
H2 = ParagraphStyle(
    "H2",
    parent=_styles["Heading2"],
    fontName="Times-Bold",
    fontSize=12,
    spaceBefore=14,
    spaceAfter=6,
    leading=14,
)
BODY = ParagraphStyle(
    "Body",
    parent=_styles["BodyText"],
    fontName="Times-Roman",
    fontSize=11,
    leading=15,
    alignment=4,  # justify
    spaceAfter=8,
)
PREAMBLE = ParagraphStyle(
    "Preamble",
    parent=BODY,
    fontName="Times-Italic",
    spaceAfter=10,
)
SIG = ParagraphStyle(
    "Sig",
    parent=BODY,
    fontName="Times-Roman",
    spaceAfter=2,
)


def _build_doc(out_path: Path) -> SimpleDocTemplate:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    return SimpleDocTemplate(
        str(out_path),
        pagesize=LETTER,
        leftMargin=1 * inch,
        rightMargin=1 * inch,
        topMargin=1 * inch,
        bottomMargin=1 * inch,
        title=out_path.stem,
        author="Caveat AI fixtures",
    )


def _signature_block(party_a: str, party_a_name: str, party_a_title: str, party_b: str = "COUNTERPARTY") -> Table:
    data = [
        [
            Paragraph(f"<b>{party_a}</b>", SIG),
            Paragraph(f"<b>{party_b}</b>", SIG),
        ],
        [
            Paragraph("By: ___________________________", SIG),
            Paragraph("By: ___________________________", SIG),
        ],
        [
            Paragraph(f"Name: {party_a_name}", SIG),
            Paragraph("Name: ___________________________", SIG),
        ],
        [
            Paragraph(f"Title: {party_a_title}", SIG),
            Paragraph("Title: ___________________________", SIG),
        ],
    ]
    table = Table(data, colWidths=[3.25 * inch, 3.25 * inch])
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


# ---- 1. Acme MSA -----------------------------------------------------------
# Planted issues:
#   (a) HIGH:    3-month liability cap                          → § 9.2
#   (b) HIGH:    one-way indemnification (Customer → Provider)  → § 10.1
#                (no reciprocal Provider → Customer obligation)
#   (c) MEDIUM:  termination for convenience, no refund         → § 8.3
#   (d) MISSING: no DPA / data-protection addendum reference    → (deliberately absent)
# Plus normal/safe clauses: Delaware governing law (§ 15.1), mutual
# confidentiality (§ 7), mutual reps (§ 3), insurance (§ 12) so the
# analyzer doesn't false-positive on benign provisions.

def msa_acme(out_path: Path) -> None:
    story: list = []
    P = lambda s: Paragraph(s, BODY)  # noqa: E731

    story.append(Paragraph("Master Services Agreement", TITLE))
    story.append(
        Paragraph(
            "This Master Services Agreement (this &ldquo;Agreement&rdquo;) is entered into as of "
            "January 15, 2026 (the &ldquo;Effective Date&rdquo;) by and between Acme Software, Inc., "
            "a Delaware corporation with its principal place of business at 100 Technology Drive, "
            "Wilmington, Delaware 19801 (&ldquo;Provider&rdquo;), and the customer identified on the "
            "applicable Order Form (&ldquo;Customer&rdquo;). Provider and Customer are each referred "
            "to herein as a &ldquo;Party&rdquo; and collectively as the &ldquo;Parties.&rdquo;",
            PREAMBLE,
        )
    )

    story.append(Paragraph("1. Definitions", H2))
    story.append(P("<b>1.1 &ldquo;Services&rdquo;</b> means the software-as-a-service offerings, professional services, and related deliverables described in one or more Order Forms executed under this Agreement."))
    story.append(P("<b>1.2 &ldquo;Order Form&rdquo;</b> means a written ordering document executed by both Parties that references this Agreement and specifies the Services to be provided, fees payable, and term."))
    story.append(P("<b>1.3 &ldquo;Documentation&rdquo;</b> means the technical and end-user documentation made generally available by Provider for the Services."))
    story.append(P("<b>1.4 &ldquo;Customer Data&rdquo;</b> means any data, content, or information submitted to or processed by the Services by or on behalf of Customer."))

    story.append(Paragraph("2. Provision of Services", H2))
    story.append(P("<b>2.1 Access.</b> Subject to the terms of this Agreement and timely payment of fees, Provider grants Customer a non-exclusive, non-transferable, non-sublicensable right during the applicable Order Form term to access and use the Services solely for Customer&rsquo;s internal business purposes."))
    story.append(P("<b>2.2 Service Levels.</b> Provider will use commercially reasonable efforts to make the Services available 99.5% of each calendar month, excluding scheduled maintenance and force majeure events. If the monthly availability falls below 99.5%, Customer&rsquo;s sole and exclusive remedy is a service credit equal to ten percent (10%) of the monthly fees for the affected month for each full percentage point below 99.5%, up to a maximum of fifty percent (50%) of the monthly fees. Service credits must be requested in writing within thirty (30) days of the affected month."))
    story.append(P("<b>2.3 Modifications to Services.</b> Provider may modify the Services from time to time, including adding, removing, or changing features, provided that Provider shall not materially diminish the core functionality of the Services during any then-current Order Form term without Customer&rsquo;s consent. Provider will use commercially reasonable efforts to provide thirty (30) days&rsquo; advance notice of material changes."))
    story.append(P("<b>2.4 Beta Features.</b> Provider may from time to time make available beta, alpha, preview, or evaluation features of the Services (&ldquo;Beta Features&rdquo;). Beta Features are provided on an &ldquo;AS IS&rdquo; basis without any warranty whatsoever, are not subject to the service-level commitments in Section 2.2, and may be modified, suspended, or discontinued at any time without notice."))
    story.append(P("<b>2.5 Support.</b> Provider will provide Customer with standard customer support during Provider&rsquo;s business hours (9:00 a.m. to 6:00 p.m. Pacific Time, Monday through Friday, excluding U.S. federal holidays). Premium support tiers, including 24/7 coverage and named technical account managers, are available pursuant to a separately executed Support Order Form.</p>"))

    story.append(Paragraph("3. Mutual Representations and Warranties", H2))
    story.append(P("<b>3.1</b> Each Party represents and warrants to the other that (a) it is duly organized and validly existing under the laws of its jurisdiction of formation; (b) it has full corporate power and authority to enter into and perform this Agreement; and (c) the execution and delivery of this Agreement has been duly authorized by all necessary corporate action."))
    story.append(P("<b>3.2</b> Provider further warrants that the Services, when used in accordance with the Documentation, will perform substantially in accordance with the Documentation. Customer&rsquo;s sole and exclusive remedy, and Provider&rsquo;s entire liability, for breach of this warranty shall be re-performance of the non-conforming Services or, if Provider is unable to re-perform within thirty (30) days, a pro-rated refund of fees paid for the non-conforming portion."))

    story.append(Paragraph("4. Fees and Payment", H2))
    story.append(P("<b>4.1 Fees.</b> Customer shall pay the fees set forth in each Order Form. Unless otherwise specified, fees are due net thirty (30) days from invoice date."))
    story.append(P("<b>4.2 Taxes.</b> Fees are exclusive of all taxes. Customer is responsible for all sales, use, value-added, and similar taxes arising out of this Agreement, excluding taxes based on Provider&rsquo;s net income."))
    story.append(P("<b>4.3 Late Payment.</b> Past-due amounts bear interest at the lesser of one and one-half percent (1.5%) per month or the maximum rate permitted by applicable law."))

    story.append(Paragraph("5. Customer Responsibilities", H2))
    story.append(P("<b>5.1</b> Customer shall (a) be responsible for all activities that occur under its accounts; (b) use the Services in compliance with all applicable laws and regulations; and (c) promptly notify Provider of any unauthorized use of its accounts or any other breach of security."))
    story.append(P("<b>5.2</b> Customer shall not (a) license, sublicense, sell, resell, rent, lease, transfer, or otherwise commercially exploit the Services; (b) modify, copy, or create derivative works of the Services; or (c) reverse engineer, decompile, or disassemble the Services, except to the extent such restriction is prohibited by applicable law."))

    story.append(Paragraph("6. Intellectual Property", H2))
    story.append(P("<b>6.1 Provider IP.</b> As between the Parties, Provider owns and shall retain all right, title, and interest in and to the Services, the Documentation, and all related intellectual property rights, including without limitation any improvements, modifications, or derivative works thereof."))
    story.append(P("<b>6.2 Customer Data.</b> As between the Parties, Customer owns and shall retain all right, title, and interest in and to the Customer Data. Customer hereby grants Provider a limited, non-exclusive, royalty-free license to use, reproduce, and process Customer Data solely as necessary to provide the Services."))
    story.append(P("<b>6.3 Feedback.</b> Customer may from time to time provide suggestions, comments, or other feedback to Provider regarding the Services (&ldquo;Feedback&rdquo;). Customer hereby grants Provider a perpetual, irrevocable, royalty-free, worldwide license to use and incorporate any Feedback into the Services."))

    story.append(Paragraph("7. Confidentiality", H2))
    story.append(P("<b>7.1 Definition.</b> &ldquo;Confidential Information&rdquo; means any non-public information disclosed by one Party (the &ldquo;Disclosing Party&rdquo;) to the other (the &ldquo;Receiving Party&rdquo;) that is identified as confidential at the time of disclosure or that, given the nature of the information and the circumstances of disclosure, should reasonably be understood to be confidential."))
    story.append(P("<b>7.2 Obligations.</b> The Receiving Party shall (a) use the Confidential Information solely for purposes of performing under this Agreement; (b) protect such Confidential Information using the same degree of care it uses to protect its own confidential information of like importance, but in no event less than a reasonable degree of care; and (c) not disclose such Confidential Information to any third party except its employees, contractors, and advisors who have a need to know and are bound by confidentiality obligations no less protective than those herein."))
    story.append(P("<b>7.3 Exceptions.</b> The obligations in Section 7.2 do not apply to information that (a) was rightfully in the Receiving Party&rsquo;s possession before disclosure; (b) is or becomes publicly available through no fault of the Receiving Party; (c) is rightfully received from a third party without confidentiality obligation; or (d) is independently developed by the Receiving Party without use of or reference to the Disclosing Party&rsquo;s Confidential Information."))
    story.append(P("<b>7.4 Survival.</b> The obligations in this Section 7 shall survive termination or expiration of this Agreement for a period of three (3) years; provided, however, that obligations with respect to trade secrets shall survive for so long as such information remains a trade secret under applicable law."))

    story.append(Paragraph("8. Term and Termination", H2))
    story.append(P("<b>8.1 Term.</b> This Agreement commences on the Effective Date and continues until terminated as set forth herein. Each Order Form shall have the term specified therein."))
    story.append(P("<b>8.2 Termination for Cause.</b> Either Party may terminate this Agreement or any Order Form upon written notice if the other Party materially breaches this Agreement and fails to cure such breach within thirty (30) days of receipt of written notice describing the breach in reasonable detail."))
    # PLANTED ISSUE (c): termination for convenience, no refund (medium)
    story.append(P("<b>8.3 Termination for Convenience.</b> Provider may terminate this Agreement or any Order Form, in whole or in part, at any time and for any reason in its sole discretion upon thirty (30) days&rsquo; prior written notice to Customer. In the event of termination for convenience by Provider, no refund of prepaid fees shall be due to Customer, and any unpaid fees for the remainder of the then-current term shall become immediately due and payable."))
    story.append(P("<b>8.4 Effect of Termination.</b> Upon termination of this Agreement, Customer&rsquo;s right to access and use the Services shall immediately cease. Within thirty (30) days following termination, Provider shall, upon Customer&rsquo;s written request, make Customer Data available for export in a commercially reasonable format. Sections 6, 7, 9, 10, 11, and 14 shall survive termination."))

    story.append(Paragraph("9. Limitation of Liability", H2))
    story.append(P("<b>9.1 Exclusion of Damages.</b> IN NO EVENT SHALL EITHER PARTY BE LIABLE TO THE OTHER FOR ANY INDIRECT, INCIDENTAL, CONSEQUENTIAL, SPECIAL, EXEMPLARY, OR PUNITIVE DAMAGES, INCLUDING WITHOUT LIMITATION DAMAGES FOR LOST PROFITS, LOST REVENUES, LOST DATA, OR BUSINESS INTERRUPTION, ARISING OUT OF OR IN CONNECTION WITH THIS AGREEMENT, REGARDLESS OF THE THEORY OF LIABILITY AND EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGES."))
    # PLANTED ISSUE (a): 3-month liability cap (high)
    story.append(P("<b>9.2 Cap on Liability.</b> EACH PARTY&rsquo;S TOTAL CUMULATIVE LIABILITY ARISING OUT OF OR RELATED TO THIS AGREEMENT, WHETHER IN CONTRACT, TORT, OR OTHERWISE, SHALL NOT EXCEED THE TOTAL AMOUNT OF FEES ACTUALLY PAID BY CUSTOMER TO PROVIDER UNDER THIS AGREEMENT IN THE THREE (3) MONTHS IMMEDIATELY PRECEDING THE EVENT GIVING RISE TO THE CLAIM."))

    story.append(Paragraph("10. Indemnification", H2))
    # PLANTED ISSUE (b): one-way indemnification (high) — no Provider→Customer mirror
    story.append(P("<b>10.1 Customer Indemnity.</b> Customer shall indemnify, defend, and hold harmless Provider, its affiliates, and their respective officers, directors, employees, and agents from and against any and all claims, losses, damages, liabilities, costs, and expenses (including reasonable attorneys&rsquo; fees) arising out of or relating to (a) Customer&rsquo;s use of the Services in violation of this Agreement or applicable law; (b) any Customer Data, including any claim that the Customer Data infringes or misappropriates any third-party intellectual property right or violates any applicable law; or (c) any breach by Customer of its representations, warranties, or obligations under this Agreement."))
    story.append(P("<b>10.2 Indemnification Procedure.</b> The indemnified Party shall promptly notify the indemnifying Party in writing of any claim subject to indemnification hereunder; provided, however, that failure to provide such notice shall not relieve the indemnifying Party of its obligations except to the extent it is materially prejudiced thereby. The indemnifying Party shall have sole control of the defense and settlement of any such claim, provided that no settlement that imposes any obligation on the indemnified Party other than the payment of money fully indemnified hereunder shall be made without the indemnified Party&rsquo;s prior written consent."))

    story.append(Paragraph("11. Mutual Confidentiality Acknowledgment", H2))
    story.append(P("Each Party acknowledges that during the term of this Agreement it may receive Confidential Information of the other Party. Each Party reaffirms its obligations set forth in Section 7 with respect to such Confidential Information and acknowledges that any breach thereof may cause irreparable harm for which monetary damages would be inadequate."))

    story.append(Paragraph("11A. Security", H2))
    story.append(P("Provider shall maintain commercially reasonable administrative, physical, and technical safeguards designed to protect the security and confidentiality of Customer Data. Such safeguards shall include, at a minimum, (a) access controls limiting access to Customer Data to Provider personnel with a legitimate need to know; (b) encryption of Customer Data at rest and in transit using industry-standard encryption algorithms; (c) regular security training for Provider personnel; and (d) an incident response program. Provider shall promptly notify Customer in writing of any actual or reasonably suspected unauthorized access to or disclosure of Customer Data within seventy-two (72) hours of becoming aware of the same."))
    story.append(P("Provider undergoes annual third-party security audits and maintains an SOC 2 Type II report, which shall be made available to Customer upon written request, subject to Customer&rsquo;s execution of a customary non-disclosure agreement covering the audit report."))

    story.append(Paragraph("11B. Subprocessors", H2))
    story.append(P("Provider may engage third-party service providers (&ldquo;Subprocessors&rdquo;) to perform certain processing activities in connection with the Services. Provider shall (a) maintain a current list of Subprocessors on its trust portal; (b) ensure that each Subprocessor is bound by written confidentiality and security obligations no less protective than those set forth in this Agreement; and (c) remain responsible for the acts and omissions of its Subprocessors as if they were Provider&rsquo;s own. Provider may add or replace Subprocessors from time to time and will provide Customer with at least thirty (30) days&rsquo; advance notice via the trust portal."))

    story.append(Paragraph("11C. Audit Rights", H2))
    story.append(P("No more than once per calendar year, and upon at least thirty (30) days&rsquo; advance written notice, Customer may, at Customer&rsquo;s expense, conduct (or engage an independent third-party auditor to conduct on Customer&rsquo;s behalf) an audit of Provider&rsquo;s compliance with the security obligations set forth in Section 11A. Such audit shall be conducted during normal business hours, in a manner that does not unreasonably interfere with Provider&rsquo;s operations, and subject to Provider&rsquo;s reasonable confidentiality and security requirements. The auditor shall execute a non-disclosure agreement directly with Provider before commencing the audit. Provider&rsquo;s most recent SOC 2 Type II report may be accepted in lieu of an on-site audit at Provider&rsquo;s discretion."))

    story.append(Paragraph("11D. Compliance with Laws; Anti-Corruption", H2))
    story.append(P("Each Party shall comply with all applicable U.S. federal, state, and local laws, rules, and regulations in connection with its performance under this Agreement, including without limitation the U.S. Foreign Corrupt Practices Act, the U.K. Bribery Act, and applicable export control laws. Neither Party shall offer, promise, or pay any bribe, kickback, or other improper benefit to any government official or commercial counterparty in connection with this Agreement."))

    story.append(Paragraph("12. Insurance", H2))
    story.append(P("Provider shall maintain, at its own expense, throughout the term of this Agreement (a) commercial general liability insurance with limits of not less than $1,000,000 per occurrence and $2,000,000 in the aggregate; (b) professional liability (errors and omissions) insurance with limits of not less than $2,000,000 per claim; and (c) workers&rsquo; compensation insurance as required by applicable law."))

    story.append(Paragraph("13. Force Majeure", H2))
    story.append(P("Neither Party shall be liable for any failure or delay in performance under this Agreement (other than payment obligations) due to causes beyond its reasonable control, including without limitation acts of God, natural disasters, war, terrorism, civil disorder, labor disputes, governmental action, or failure of telecommunications or third-party hosting services. The affected Party shall use reasonable efforts to resume performance as soon as practicable."))

    story.append(Paragraph("14. Independent Contractors; Assignment", H2))
    story.append(P("<b>14.1 Independent Contractors.</b> The Parties are independent contractors. Nothing in this Agreement creates a partnership, joint venture, agency, franchise, or employment relationship between the Parties."))
    story.append(P("<b>14.2 Assignment.</b> Neither Party may assign this Agreement, in whole or in part, without the other Party&rsquo;s prior written consent, which shall not be unreasonably withheld; provided, however, that either Party may assign this Agreement without consent to a successor in connection with a merger, acquisition, corporate reorganization, or sale of all or substantially all of its assets."))

    story.append(Paragraph("15. General", H2))
    story.append(P("<b>15.1 Governing Law; Venue.</b> This Agreement shall be governed by and construed in accordance with the laws of the State of Delaware, without regard to its conflict-of-laws principles. The Parties consent to the exclusive jurisdiction of the state and federal courts located in Wilmington, Delaware for any dispute arising out of or relating to this Agreement."))
    story.append(P("<b>15.2 Notices.</b> All notices under this Agreement shall be in writing and shall be deemed given when delivered personally, sent by confirmed electronic mail to the addresses set forth on the Order Form, or sent by nationally recognized overnight courier."))
    story.append(P("<b>15.3 Entire Agreement.</b> This Agreement, together with all Order Forms executed hereunder, constitutes the entire agreement between the Parties with respect to its subject matter and supersedes all prior or contemporaneous agreements, proposals, or representations, whether written or oral, concerning such subject matter."))
    story.append(P("<b>15.4 Amendment; Waiver.</b> No amendment to this Agreement shall be effective unless in writing and signed by both Parties. No waiver of any provision shall be effective unless in writing and signed by the waiving Party."))
    story.append(P("<b>15.5 Severability.</b> If any provision of this Agreement is held to be invalid or unenforceable, such provision shall be modified to the minimum extent necessary to make it enforceable, and the remaining provisions shall remain in full force and effect."))
    story.append(P("<b>15.6 Counterparts; Electronic Signature.</b> This Agreement may be executed in any number of counterparts, each of which shall be deemed an original and all of which together shall constitute one and the same instrument. Counterparts may be exchanged by facsimile, electronic mail, or recognized electronic-signature service, and any such transmitted signature shall be deemed an original signature for all purposes."))
    story.append(P("<b>15.7 Headings.</b> Section headings are for reference only and shall not affect the interpretation of this Agreement. References to a Section number include all subsections of such Section unless the context requires otherwise."))
    story.append(P("<b>15.8 No Third-Party Beneficiaries.</b> This Agreement is for the sole benefit of the Parties and their permitted successors and assigns, and nothing herein, express or implied, is intended to or shall confer upon any other person any legal or equitable right, benefit, or remedy of any nature whatsoever."))
    story.append(P("<b>15.9 Publicity.</b> Neither Party shall issue any press release, public announcement, or use the other Party&rsquo;s name or logo in any marketing materials, customer lists, or case studies without the other Party&rsquo;s prior written consent, which shall not be unreasonably withheld. Provider may, however, list Customer&rsquo;s name and logo on Provider&rsquo;s general customer list on Provider&rsquo;s website."))
    story.append(P("<b>15.10 Order of Precedence.</b> In the event of any conflict between the terms of this Agreement and any Order Form, the terms of this Agreement shall control unless the Order Form expressly references the conflicting provision and states that it is intended to supersede it."))

    story.append(Paragraph("16. Dispute Resolution", H2))
    story.append(P("<b>16.1 Informal Resolution.</b> The Parties shall attempt in good faith to resolve any dispute arising out of or relating to this Agreement through informal discussions between senior executives of each Party. If the dispute is not resolved within thirty (30) days after written notice from one Party to the other, either Party may pursue any other remedy available under this Agreement or at law or in equity."))
    story.append(P("<b>16.2 Equitable Relief.</b> Notwithstanding Section 16.1, either Party may seek injunctive or other equitable relief at any time, in any court of competent jurisdiction, to protect its intellectual property rights, Confidential Information, or to prevent irreparable harm."))
    story.append(P("<b>16.3 Attorneys&rsquo; Fees.</b> In any action brought to enforce this Agreement, the prevailing Party shall be entitled to recover its reasonable attorneys&rsquo; fees and costs incurred in connection with such action, in addition to any other relief awarded."))

    story.append(Paragraph("17. Records and Cooperation", H2))
    story.append(P("Provider shall maintain accurate books and records relating to the Services and the fees charged hereunder for a period of three (3) years after the termination or expiration of this Agreement. Each Party shall provide the other with reasonable cooperation and information necessary for the other Party to comply with its obligations under this Agreement, including without limitation responding to legitimate audit, regulatory, or investigatory inquiries."))
    # PLANTED ISSUE (d): NO § for Data Protection Addendum (DPA) — deliberately absent.

    story.append(Spacer(1, 0.25 * inch))
    story.append(P("IN WITNESS WHEREOF, the Parties have caused this Agreement to be executed by their duly authorized representatives as of the Effective Date."))
    story.append(Spacer(1, 0.15 * inch))
    story.append(_signature_block("ACME SOFTWARE, INC.", "Patricia Thornton", "Chief Executive Officer"))

    _build_doc(out_path).build(story)


# ---- 2. TechCorp NDA -------------------------------------------------------
# Planted issues:
#   (a) MEDIUM: overly broad "Confidential Information" definition  → § 1
#   (b) MEDIUM: survival period absent / unclear                     → no § for survival

def nda_techcorp(out_path: Path) -> None:
    story: list = []
    P = lambda s: Paragraph(s, BODY)  # noqa: E731

    story.append(Paragraph("Mutual Non-Disclosure Agreement", TITLE))
    story.append(
        Paragraph(
            "This Mutual Non-Disclosure Agreement (this &ldquo;Agreement&rdquo;) is made effective "
            "as of February 3, 2026 (the &ldquo;Effective Date&rdquo;) by and between TechCorp "
            "Industries, Inc., a New York corporation (&ldquo;TechCorp&rdquo;), and the counterparty "
            "identified on the signature page below (&ldquo;Counterparty&rdquo;). The parties wish to "
            "discuss a potential business relationship and may exchange Confidential Information as "
            "defined below. Each party may act as either Disclosing Party or Receiving Party.",
            PREAMBLE,
        )
    )

    story.append(Paragraph("1. Definition of Confidential Information", H2))
    # PLANTED ISSUE (a): overly broad CI definition (medium)
    story.append(P("&ldquo;Confidential Information&rdquo; means any and all information disclosed by either party to the other party, whether marked as confidential or not, in any form, by any means, whether oral, written, electronic, visual, tangible, or intangible, including without limitation business plans, strategies, financial information, product information, technical information, customer lists, supplier lists, employee information, and any and all other information of any nature whatsoever that is exchanged between the parties at any time before, during, or after the term of this Agreement, regardless of whether such information would ordinarily be considered confidential or proprietary in nature."))

    story.append(Paragraph("2. Exceptions", H2))
    story.append(P("The obligations of the Receiving Party set forth in Section 3 shall not apply to information that the Receiving Party can demonstrate, by competent written evidence:"))
    story.append(P("(a) was lawfully in the Receiving Party&rsquo;s possession prior to disclosure by the Disclosing Party, free of any obligation of confidentiality;"))
    story.append(P("(b) is or becomes publicly available through no fault, act, or omission of the Receiving Party;"))
    story.append(P("(c) is lawfully received by the Receiving Party from a third party who has the right to disclose it and who imposes no confidentiality obligation;"))
    story.append(P("(d) is independently developed by the Receiving Party without any use of or reference to the Disclosing Party&rsquo;s Confidential Information; or"))
    story.append(P("(e) is required to be disclosed pursuant to applicable law, regulation, or valid court order, provided that the Receiving Party gives the Disclosing Party prompt written notice (where legally permitted) and reasonable cooperation in seeking a protective order."))

    story.append(Paragraph("3. Obligations of the Receiving Party", H2))
    story.append(P("<b>3.1 Use Restriction.</b> The Receiving Party shall use the Confidential Information solely for the purpose of evaluating and pursuing the potential business relationship between the parties and for no other purpose."))
    story.append(P("<b>3.2 Standard of Care.</b> The Receiving Party shall protect the Confidential Information using the same degree of care it uses to protect its own confidential information of like importance, but in no event less than a reasonable degree of care."))
    story.append(P("<b>3.3 Limited Disclosure.</b> The Receiving Party shall limit access to the Confidential Information to its employees, contractors, advisors, and representatives who (a) have a bona fide need to know such information for the purpose set forth in Section 3.1, and (b) are bound by written or professional confidentiality obligations no less protective than those set forth in this Agreement."))

    story.append(Paragraph("4. No License; No Warranty", H2))
    story.append(P("<b>4.1</b> Nothing in this Agreement shall be construed as granting any license, expressly or by implication, under any patent, copyright, trademark, trade secret, or other intellectual property right of the Disclosing Party."))
    story.append(P("<b>4.2</b> The Disclosing Party makes no representations or warranties, express or implied, regarding the accuracy or completeness of the Confidential Information."))

    story.append(Paragraph("5. Mutual Remedies", H2))
    story.append(P("Each party acknowledges that any breach of this Agreement by the Receiving Party may cause the Disclosing Party irreparable harm for which monetary damages would be an inadequate remedy. Accordingly, the Disclosing Party shall be entitled to seek injunctive or other equitable relief, in addition to any other remedies available at law or in equity, without the necessity of posting a bond. The remedies available under this Section 5 are mutual and shall apply equally to either party in its capacity as Disclosing Party."))

    story.append(Paragraph("6. Return or Destruction", H2))
    story.append(P("Upon the Disclosing Party&rsquo;s written request, or upon termination of the discussions between the parties, the Receiving Party shall promptly return or destroy all Confidential Information of the Disclosing Party in the Receiving Party&rsquo;s possession, custody, or control, and certify such return or destruction in writing. Notwithstanding the foregoing, the Receiving Party may retain Confidential Information to the extent required by applicable law or its bona fide internal records retention policies, provided that any such retained Confidential Information shall remain subject to the confidentiality obligations of this Agreement for so long as it is retained."))

    story.append(Paragraph("7. Governing Law and Venue", H2))
    story.append(P("This Agreement shall be governed by and construed in accordance with the laws of the State of New York, without regard to its conflict-of-laws principles. The parties consent to the exclusive jurisdiction of the state and federal courts located in New York County, New York for any dispute arising out of or relating to this Agreement."))

    story.append(Paragraph("8. Miscellaneous", H2))
    story.append(P("<b>8.1 Entire Agreement.</b> This Agreement constitutes the entire agreement between the parties with respect to its subject matter and supersedes all prior or contemporaneous agreements, proposals, or representations concerning such subject matter."))
    story.append(P("<b>8.2 Amendment.</b> No amendment to this Agreement shall be effective unless in writing and signed by both parties."))
    story.append(P("<b>8.3 Severability.</b> If any provision of this Agreement is held invalid or unenforceable, such provision shall be modified to the minimum extent necessary to make it enforceable, and the remaining provisions shall remain in full force and effect."))
    # PLANTED ISSUE (b): NO § for survival period — deliberately absent.

    story.append(Spacer(1, 0.25 * inch))
    story.append(P("IN WITNESS WHEREOF, the parties have executed this Agreement as of the Effective Date."))
    story.append(Spacer(1, 0.15 * inch))
    story.append(_signature_block("TECHCORP INDUSTRIES, INC.", "Marcus Whitfield", "General Counsel"))

    _build_doc(out_path).build(story)


# ---- 3. Invoice (not a contract) -------------------------------------------
# Single-page commercial invoice. Used to test classifier edge case
# "Other / not a contract" (FR-004 + spec edge cases).

INV_HEAD = ParagraphStyle("InvHead", parent=BODY, fontName="Times-Bold", fontSize=18, alignment=2, spaceAfter=4)
INV_LBL = ParagraphStyle("InvLbl", parent=BODY, fontName="Times-Bold", fontSize=12, spaceAfter=2)


def invoice(out_path: Path) -> None:
    story: list = []
    P = lambda s: Paragraph(s, BODY)  # noqa: E731

    header = Table(
        [
            [
                Paragraph(
                    "<b><font size='14'>Northbrook Office Supplies, Inc.</font></b><br/>"
                    "245 Industrial Parkway<br/>"
                    "Northbrook, IL 60062<br/>"
                    "hello@northbrooksupplies.com &middot; (847) 555-0142",
                    BODY,
                ),
                Paragraph(
                    "<b><font size='18'>INVOICE</font></b><br/>"
                    "Invoice #: INV-2026-04127<br/>"
                    "Date: April 22, 2026<br/>"
                    "Due: May 22, 2026<br/>"
                    "Terms: Net 30",
                    ParagraphStyle("RAlign", parent=BODY, alignment=2),
                ),
            ]
        ],
        colWidths=[3.5 * inch, 3.0 * inch],
    )
    header.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(header)
    story.append(Spacer(1, 0.25 * inch))

    story.append(P("<b>Bill To:</b><br/>Riverside Marketing Group<br/>Attn: Accounts Payable<br/>1820 W. Fulton Street, Suite 400<br/>Chicago, IL 60612"))
    story.append(Spacer(1, 0.2 * inch))

    line_items = Table(
        [
            ["Description", "Qty", "Unit Price", "Total"],
            ["Premium Letter Paper, 20 lb, 5,000 ct (case)", "4", "$48.00", "$192.00"],
            ["Black Ink Cartridge, HP 64XL (compatible)", "12", "$26.50", "$318.00"],
            ["Heavy-Duty Stapler, full strip", "3", "$32.00", "$96.00"],
            ["Manila File Folders, letter, box of 100", "2", "$18.50", "$37.00"],
            ["Standard delivery (Northbrook to Chicago, 04/22)", "1", "$24.00", "$24.00"],
        ],
        colWidths=[3.5 * inch, 0.7 * inch, 1.1 * inch, 1.2 * inch],
    )
    line_items.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), "Times-Bold"),
                ("BACKGROUND", (0, 0), (-1, 0), (0.92, 0.92, 0.92)),
                ("LINEBELOW", (0, 0), (-1, -1), 0.5, (0.4, 0.4, 0.4)),
                ("FONTNAME", (0, 1), (-1, -1), "Times-Roman"),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(line_items)
    story.append(Spacer(1, 0.15 * inch))

    totals = Table(
        [
            ["Subtotal:", "$667.00"],
            ["Sales Tax (10.25%):", "$68.37"],
            ["Total Due:", "$735.37"],
        ],
        colWidths=[3.0 * inch, 1.5 * inch],
        hAlign="RIGHT",
    )
    totals.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Times-Roman"),
                ("ALIGN", (-1, 0), (-1, -1), "RIGHT"),
                ("LINEABOVE", (0, -1), (-1, -1), 1.5, (0, 0, 0)),
                ("FONTNAME", (0, -1), (-1, -1), "Times-Bold"),
                ("FONTSIZE", (0, -1), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(totals)
    story.append(Spacer(1, 0.4 * inch))
    story.append(
        Paragraph(
            "<font size='10' color='#666666'>Please remit payment to the address above. Wire transfer details available on request. Thank you for your business.</font>",
            BODY,
        )
    )

    _build_doc(out_path).build(story)


# ---- 4. Real EDGAR MSA (pseudonymized) -------------------------------------
# Source: SEC EDGAR Exhibit 10.13 (Kubient/Sphere Digital MSA, June 2018,
# Accession 0001104659-20-080690). SEC filings are public domain. Party
# names are pseudonymized to keep the fixture neutral; structure and
# language are intact.
#
# Source text lives at fixtures/raw/edgar-msa-source.txt for offline
# reproducibility — see fixtures/contracts/README.md for provenance.
# Used in the manual validation scenarios only (real Gemma 4 hits this).
# No issues are deliberately planted; the analyzer is left to find what
# it finds.

RAW_SOURCE = Path(__file__).parent / "raw" / "edgar-msa-source.txt"

EDGAR_BODY = ParagraphStyle(
    "EdgarBody",
    parent=BODY,
    fontName="Times-Roman",
    fontSize=10,
    leading=13,
    alignment=4,  # justify
    spaceAfter=6,
)
EDGAR_CENTER = ParagraphStyle(
    "EdgarCenter",
    parent=EDGAR_BODY,
    alignment=1,  # center
    spaceBefore=4,
    spaceAfter=8,
)
EDGAR_RIGHT = ParagraphStyle(
    "EdgarRight",
    parent=EDGAR_BODY,
    alignment=2,  # right
    spaceAfter=4,
)


def real_msa_edgar(out_path: Path) -> None:
    if not RAW_SOURCE.exists():
        raise FileNotFoundError(
            f"Missing source text {RAW_SOURCE}. The EDGAR MSA source is committed; "
            "if you removed it, regenerate from the SEC filing."
        )
    story: list = []
    text = RAW_SOURCE.read_text()
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        style = EDGAR_BODY
        if line.startswith("[CENTER]"):
            line = line[len("[CENTER]"):].strip()
            style = EDGAR_CENTER
        elif line.startswith("[RIGHT]"):
            line = line[len("[RIGHT]"):].strip()
            style = EDGAR_RIGHT
        story.append(Paragraph(line, style))
    _build_doc(out_path).build(story)


def main() -> None:
    print(f"Building fixtures into {OUT_DIR}/ ...")
    msa_acme(OUT_DIR / "msa-acme.pdf")
    print(f"  wrote msa-acme.pdf  ({(OUT_DIR / 'msa-acme.pdf').stat().st_size / 1024:.1f} KB)")
    nda_techcorp(OUT_DIR / "nda-techcorp.pdf")
    print(f"  wrote nda-techcorp.pdf  ({(OUT_DIR / 'nda-techcorp.pdf').stat().st_size / 1024:.1f} KB)")
    invoice(OUT_DIR / "invoice-not-a-contract.pdf")
    print(f"  wrote invoice-not-a-contract.pdf  ({(OUT_DIR / 'invoice-not-a-contract.pdf').stat().st_size / 1024:.1f} KB)")
    real_msa_edgar(OUT_DIR / "real-msa-edgar.pdf")
    print(f"  wrote real-msa-edgar.pdf  ({(OUT_DIR / 'real-msa-edgar.pdf').stat().st_size / 1024:.1f} KB)")
    print("Done.")


if __name__ == "__main__":
    main()
