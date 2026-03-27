#######################
#                     #
#     LLM As Jury     #
#                     #
#######################

# Library Imports

from llmproxy import LLMProxy
from time import sleep
from string import Template
import json

# Class Definition

class Magi:
    """ 
    Magi is the Jury of LLMs that will provide different insight on the results of our
    main LLM. Each of the different models have a slight difference in the way that they're
    prompted, as in a way to create possible variety within the system. Magi is composed
    of the following three LLMs:

    * Melchior: This is the ChatGPT model.
    * Casper: This is the Claude Haiku model.
    * Balthazar: This is the Lorem Ipsum model.
    """

    def __init__(self) -> None:

        self.client = LLMProxy()
        self.session = "Magi_Iudicantes_Session"

    def rag_context_string_simple(self, context) -> str:

        """
        Convert the RAG context list (from retrieve API)
        into a single plain-text string that can be appended to a query.
        This function was taken from the example file retrieve_and_generate.py
        """
        
        context_string = ""

        i=1

        for collection in context:
    
            if not context_string:
                context_string = """The following is additional context that may be helpful in answering the user's query."""

            context_string += """
            #{} {}
            """.format(i, collection['doc_summary'])
            j=1
        
            for chunk in collection['chunks']:
                context_string+= """
                #{}.{} {}
                """.format(i,j, chunk)
                j+=1
        
            i+=1
        
        return context_string

    def query_context(self, context_string) -> str:

        """
        Lorem ipsum function, helps to make it work
        """
        address = "lorem/ipsum/address.json"
        
        with open(address, mode="r", encoding="utf-8") as t:
            
            rag_context = json.load(t)
        
        self.client.upload_text(rag_context,
                                session_id="RAG",
                                strategy="smart")
        print("Thinking...")

        sleep(20)

        query = "very lorem, so ipsum."

        rag_context = self.client.retrieve(
        query = query,
        session_id='RAG',
        rag_threshold = 0.6,
        rag_k = 4
        )

        self.query_and_context = Template("$query\n$rag_context").substitute(
                            query=query,
                            rag_context= self.rag_context_string_simple(rag_context)
                            )

        return self.query_and_context   

    def Melchior(self) -> dict:
    
        """
        As stated previously, this is the ChatGPT member of Jury.

        Input:

        Output:
        """

        melchior_maxim = self.client.generate(
            model = "4o-mini",
            system = "You are a severe, yet helpful member of an academic jury.",
            query = "",
            temperature= 0.5,
            lastk= 3,
            session_id = self.session,
            rag_usage= True
        )
        return melchior_maxim
    
    def Casper(self) -> dict:
    
            """
            As stated previously, this is the Claude Haiku member of Jury.

            Input:

            Output:
            """

            casper_maxim = self.client.generate(
                model = "us.anthropic.claude-3-haiku-20240307-v1:0",
                system = "You are a benevolent, yet helpful member of an academic jury.",
                query = "",
                temperature= 0.5,
                lastk= 3,
                session_id = self.session,
                rag_usage= True
            )
            return casper_maxim
    
    def Balthazar(self) -> dict:
    
            """
            As stated previously, this is the lorem ipsum member of Jury.

            Input:

            Output:
            """

            balthazar_maxim = self.client.generate(
                model = "Loremipsum",
                system = "You are a benevolent, yet helpful member of an academic jury.",
                query = "",
                temperature= 0.5,
                lastk= 3,
                session_id = self.session,
                rag_usage= True
            )
            return balthazar_maxim
