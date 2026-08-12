from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import SerperDevTool

@CrewBase
class YoutubeArchitect():
    """YoutubeArchitect crew"""

    # We use the CrewAI LLM class to ensure perfect compatibility with Pydantic
    # and to direct all traffic to your local Ollama instance.
    llm = LLM(
        model="ollama/gemma4:latest",
        base_url="http://localhost:11434"
    )

    @agent
    def trend_analyst(self) -> Agent:
        return Agent(
            config=self.agents_config['trend_analyst'],
            tools=[SerperDevTool()], 
            verbose=True,
            llm=self.llm
        )

    @agent
    def narrative_designer(self) -> Agent:
        return Agent(
            config=self.agents_config['narrative_designer'],
            verbose=True,
            llm=self.llm
        )

    @agent
    def seo_strategist(self) -> Agent:
        return Agent(
            config=self.agents_config['seo_strategist'],
            verbose=True,
            llm=self.llm
        )

    @task
    def research_task(self) -> Task:
        return Task(
            config=self.tasks_config['research_task'],
        )

    @task
    def scripting_task(self) -> Task:
        return Task(
            config=self.tasks_config['scripting_task'],
        )

    @task
    def seo_task(self) -> Task:
        return Task(
            config=self.tasks_config['seo_task'],
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )