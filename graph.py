from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
from rag import retrieve_context
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from agents import build_planner_agent
from agents import build_gap_analysis_agent
from agents import build_fact_checker_agent
from concurrent.futures import ThreadPoolExecutor
from functools import partial

class ResearchState(TypedDict):
    topic: str
    research_questions: list[str]
    search_results: list[str]
    articles: list[str]
    report: str
    critique: str
    revision_count: int
    research_gaps: str
    fact_check: str
    use_uploaded_docs: bool
    selected_document_ids: list[str]

def normalize_url(url: str) -> str:
    """Normalize URLs so equivalent links can be identified as duplicates."""
    try:
        parsed = urlparse(url.strip())

        if parsed.scheme.lower() not in ("http", "https"):
            return ""

        hostname = (parsed.hostname or "").lower()

        if not hostname:
            return ""

        # Treat www.example.com and example.com as the same host.
        if hostname.startswith("www."):
            hostname = hostname[4:]

        # Remove common tracking parameters.
        tracking_prefixes = ("utm_",)
        tracking_params = {
            "fbclid",
            "gclid",
            "dclid",
            "mc_cid",
            "mc_eid",
        }

        query_params = [
            (key, value)
            for key, value in parse_qsl(
                parsed.query,
                keep_blank_values=True,
            )
            if key.lower() not in tracking_params
            and not key.lower().startswith(tracking_prefixes)
        ]

        path = parsed.path.rstrip("/") or "/"

        # Fragments are excluded because they usually identify
        # a section of the same page, not a separate article.
        return urlunparse((
            "https",
            hostname,
            path,
            "",
            urlencode(sorted(query_params)),
            "",
        ))

    except (ValueError, TypeError):
        return ""    

def to_text(value):
    """Convert strings or lists of text blocks into a string."""
    if isinstance(value, str):
        return value

    if isinstance(value, list):
        parts = []

        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                if item.get("type") == "text":
                    parts.append(item.get("text", ""))
            else:
                parts.append(str(item))

        return "\n".join(parts)

    if value is None:
        return ""

    return str(value)

def planner_node(state: ResearchState):
    print("\n--- PLANNER NODE ---")

    planner = build_planner_agent()

    result = planner.invoke({
        "messages": [
            {
                "role": "user",
                "content": f"""
Create a research plan for:

{state["topic"]}
"""
            }
        ]
    })

    planner_output = result["messages"][-1].content

    if isinstance(planner_output, list):
        text_parts = []

        for block in planner_output:
            if isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(block.get("text", ""))

        planner_output = "\n".join(text_parts)

    questions = []

    for line in planner_output.splitlines():
        line = line.strip()

        if line and line[0].isdigit() and "." in line:
            question = line.split(".", 1)[1].strip()

            if question:
                questions.append(question)

    return {
        "research_questions": questions
    }


def search_node(state: ResearchState):
    print("\n--- SEARCH NODE ---")

    from tools import web_search

    questions = state.get("research_questions", [])[:4]

    if not questions:
        print("No research questions were generated.")
        return {"search_results": []}

    def run_search(question):
        print(f"Searching: {question}")
        return web_search.invoke({"query": question})

    with ThreadPoolExecutor(max_workers=4) as executor:
        raw_results = list(executor.map(run_search, questions))

    unique_results = []
    seen_urls = set()

    for search_result in raw_results:
        if not isinstance(search_result, str):
            continue

        # Each search result may contain multiple articles.
        current_result = []
        current_url = None

        for line in search_result.splitlines():
            stripped_line = line.strip()

            if stripped_line.startswith("Title:") or stripped_line.startswith("Title :"):
                # Save the previous article before starting another.
                if current_result and current_url:
                    normalized = normalize_url(current_url)

                    if normalized and normalized not in seen_urls:
                        seen_urls.add(normalized)
                        unique_results.append("\n".join(current_result))

                current_result = [stripped_line]
                current_url = None

            elif stripped_line.startswith("URL:") or stripped_line.startswith("URL :"):
                current_result.append(stripped_line)
                current_url = stripped_line.split(":", 1)[1].strip()

            elif current_result:
                current_result.append(line)

        # Save the final article in this search result.
        if current_result and current_url:
            normalized = normalize_url(current_url)

            if normalized and normalized not in seen_urls:
                seen_urls.add(normalized)
                unique_results.append("\n".join(current_result))

    print(f"Search questions processed: {len(questions)}")
    print(f"Unique articles found: {len(unique_results)}")

    return {"search_results": unique_results}


def reader_node(state: ResearchState):
    print("\n--- READER NODE ---")

    from tools import scrape_url

    articles = []
    seen_urls = set()

    search_results = state.get("search_results", [])

    print("Number of unique search results:", len(search_results))

    for search_result in search_results:
        if not isinstance(search_result, str):
            continue

        url = None

        for line in search_result.splitlines():
            line = line.strip()

            if line.startswith("URL:") or line.startswith("URL :"):
                url = line.split(":", 1)[1].strip()
                break

        if not url:
            continue

        normalized = normalize_url(url)

        if not normalized or normalized in seen_urls:
            print(f"Skipping duplicate URL: {url}")
            continue

        seen_urls.add(normalized)

        print(f"\nReading: {url}")

        try:
            content = scrape_url.invoke({"url": url})

            if not isinstance(content, str):
                content = str(content)

            if not content.strip():
                print(f"No content extracted from: {url}")
                continue

            if content.startswith("Could not scrape URL:"):
                print(content)
                continue

            articles.append(
                f"URL: {url}\n"
                f"CONTENT:\n{content}"
            )

        except Exception as exc:
            print(f"Could not read {url}: {exc}")

    print(f"Unique articles successfully collected: {len(articles)}")

    return {"articles": articles}



def gap_analysis_node(state: ResearchState):
    print("\n--- GAP ANALYSIS NODE ---")

    gap_agent = build_gap_analysis_agent()

    result = gap_agent.invoke({
        "messages": [{
            "role": "user",
            "content": f"""
            Research topic:
            {state["topic"]}

            Research questions:
            {state.get("research_questions", [])}

            Search results:
            {state.get("search_results", [])}

            Collected articles:
            {state.get("articles", [])}

            Identify unanswered questions, missing evidence,
            weak sources, conflicting findings, and areas
            that need further research.

            Do not invent facts or citations.
            """
        }]
    })

    research_gaps = to_text(result["messages"][-1].content)

    print("\nResearch gaps identified:")
    print(research_gaps)

    return {
        "research_gaps": research_gaps
    }


def fact_checker_node(state: ResearchState):
    print("\n--- FACT CHECKER NODE ---")

    checker = build_fact_checker_agent()

    result = checker.invoke({
        "messages": [{
            "role": "user",
            "content": f"""
            Research topic:
            {state["topic"]}

            Research evidence:
            {state.get("articles", [])}

            Search results:
            {state.get("search_results", [])}

            Draft report:
            {state.get("report", "")}

            Check factual claims against the available evidence.
            Flag unsupported claims, conflicting findings,
            inaccurate statistics, and claims that cannot
            be verified.

            Do not invent evidence or citations.
            """
        }]
    })

    fact_check = to_text(result["messages"][-1].content)

    print("\nFact-check results:")
    print(fact_check)

    return {
        "fact_check": fact_check
    }





def writer_node(state: ResearchState):
    print("\n--- WRITER NODE ---")

    from agents import writer_chain

    # Existing evidence gathered from web research.
    research = "\n\n".join(
        article[:1500]
        for article in state["articles"][:6]
    )

    # Retrieve PDF evidence only when the user enables it.
    if state.get("use_uploaded_docs", False):
        queries = [
            state["topic"],
            *state.get("research_questions", [])[:4],
        ]

        pdf_passages = []
        seen_passages = set()

        for query in queries:
            passages = retrieve_context(
                query,
                top_k=3,
                distance_threshold=0.65,
                document_ids=state.get("selected_document_ids"),
            )

            for passage in passages:
                passage_key = (
                    passage["document_id"],
                    passage["page"],
                    passage["text"],
                )

                if passage_key in seen_passages:
                    continue

                seen_passages.add(passage_key)
                pdf_passages.append(passage)

        if pdf_passages:
            pdf_evidence = "\n\n".join(
                (
                    f"PDF SOURCE: {item['filename']}, "
                    f"page {item['page']}\n"
                    f"CONTENT: {item['text']}"
                )
                for item in pdf_passages
            )

            research += (
                "\n\nUPLOADED PDF EVIDENCE:\n"
                + pdf_evidence
            )
        

    critique = state.get("critique", "")

    report = writer_chain.invoke({
        "topic": state["topic"],
        "research": research,
        "critique": critique,
    })

    return {
        "report": report,
        "revision_count": state.get("revision_count", 0) + 1,
    }




def critic_node(state: ResearchState):
    print("\n--- CRITIC NODE ---")

    from agents import critic_chain

    report_with_checks = (
        f"DRAFT REPORT:\n{state['report']}\n\n"
        f"FACT-CHECK FINDINGS:\n"
        f"{state.get('fact_check', 'No fact-check available.')}"
    )

    critique = critic_chain.invoke({
        "report": report_with_checks
    })

    return {"critique": critique}


def critic_decision(state: ResearchState):
    critique = state["critique"]

    if "Score:" in critique:
        try:
            score_text = critique.split("Score:")[1].split("/")[0].strip()
            score = float(score_text)

            if score >= 7:
                return "end"

        except ValueError:
            pass

    if state.get("revision_count", 0) >= 1:
        return "end"

    return "revise"

graph_builder = StateGraph(ResearchState)


graph_builder.add_node("planner", planner_node)
graph_builder.add_node("search", search_node)
graph_builder.add_node("reader", reader_node)
graph_builder.add_node("gap_analysis", gap_analysis_node)
graph_builder.add_node("fact_checker", fact_checker_node)
graph_builder.add_node("writer", writer_node)
graph_builder.add_node("critic", critic_node)


graph_builder.add_edge(START, "planner")
graph_builder.add_edge("planner", "search")
graph_builder.add_edge("search", "reader")
graph_builder.add_edge("reader", "gap_analysis")
graph_builder.add_edge("gap_analysis", "writer")
graph_builder.add_edge("writer", "fact_checker")
graph_builder.add_edge("fact_checker", "critic")


graph_builder.add_conditional_edges(
    "critic",
    critic_decision,
    {
        "end": END,
        "revise": "writer"
    }
)

graph = graph_builder.compile()



if __name__ == "__main__":
    result = graph.invoke({
        "topic": "Impact of Generative AI on Software Engineering",
        "revision_count": 0
    })

    print("\n--- RESEARCH QUESTIONS ---")

    for i, question in enumerate(result["research_questions"], 1):
        print(f"{i}. {question}")

    print("\n--- SEARCH RESULTS ---")
    for i, search_result in enumerate(result["search_results"], 1):
        print(f"\n### Question {i}")
        print(search_result[:1000])

    print("\n--- ARTICLES ---")
    print(f"Total articles collected: {len(result['articles'])}")

    for i, article in enumerate(result["articles"], 1):
        first_line = article.split("\n")[0]
        print(f"Article {i}: {first_line}")

    print("\n--- FINAL REPORT ---")
    print(result["report"])
    print("\n--- RESEARCH GAPS ---")
    print(result.get("research_gaps", ""))

    print("\n--- FACT-CHECK RESULTS ---")
    print(result.get("fact_check", ""))
    print("\n--- CRITIQUE ---")
    print(result["critique"])