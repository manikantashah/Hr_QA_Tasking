import os
from langchain_oci import ChatOCIGenAI
from dotenv import load_dotenv
load_dotenv()

CONFIG = os.getenv("ConfigPath")

llm = ChatOCIGenAI(

    

    model_id="cohere.command-a-03-2025",
    service_endpoint="https://inference.generativeai.eu-frankfurt-1.oci.oraclecloud.com",
    compartment_id="ocid1.compartment.oc1..aaaaaaaa2jjkoqmd23eccvazv4u6dx746sx7ltkytcxb7swfjibcqdvw6blq",
    auth_profile="DEFAULT",
    auth_file_location= CONFIG, 
    model_kwargs={"max_tokens": 4000}
)

