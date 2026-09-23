from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from agents import build_planner_agent


class ResearchState(TypedDict):
    topic: str
    research_questions: list[str]
    search_results: list[str]
    articles: list[str]
    report: str
    critique: str
    revision_count: int


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

    search_results = []

    for question in state["research_questions"]:
        print(f"\nSearching: {question}")

        result = web_search.invoke({
            "query": question
        })

        search_results.append(result)

    return {"search_results": search_results}

def reader_node(state: ResearchState):
    print("\n--- READER NODE ---")

    from tools import scrape_url

    articles = []

    print("Number of search results:", len(state["search_results"]))
    print("First search result:")
    print(state["search_results"][0])   

    for search_result in state["search_results"]:
        lines = search_result.splitlines()

        for line in lines:
            line = line.strip()

            if line.startswith("URL:"):
                url = line.replace("URL:", "").strip()

                print(f"\nReading: {url}")

                content = scrape_url.invoke({
                    "url": url
                })

                articles.append(
                    f"URL: {url}\nCONTENT:\n{content}"
                )

    return {"articles": articles}

def writer_node(state: ResearchState):
    print("\n--- WRITER NODE ---")

    from agents import writer_chain

    research = "\n\n".join(state["articles"])

    critique = state.get("critique", "")

    report = writer_chain.invoke({
        "topic": state["topic"],
        "research": research,
        "critique": critique
    })

    return {
        "report": report,
        "revision_count": state.get("revision_count", 0) + 1
    }

def critic_node(state: ResearchState):
    print("\n--- CRITIC NODE ---")

    from agents import critic_chain

    critique = critic_chain.invoke({
        "report": state["report"]
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

    if state.get("revision_count", 0) >= 2:
        return "end"

    return "revise"

graph_builder = StateGraph(ResearchState)

graph_builder.add_node("planner", planner_node)
graph_builder.add_node("search", search_node)
graph_builder.add_node("reader", reader_node)
graph_builder.add_node("writer", writer_node)
graph_builder.add_node("critic", critic_node)

graph_builder.add_edge(START, "planner")
graph_builder.add_edge("planner", "search")
graph_builder.add_edge("search", "reader")
graph_builder.add_edge("reader", "writer")
graph_builder.add_edge("writer", "critic")

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

    print("\n--- CRITIQUE ---")
    print(result["critique"])