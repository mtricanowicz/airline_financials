# app/Dockerfile

# A Dockerfile must start with a FROM instruction. It sets the Base Image (think OS) for the container:
FROM python:3.12

# The WORKDIR instruction sets the working directory for any RUN, CMD, ENTRYPOINT, COPY and ADD instructions that follow it in the Dockerfile . Let’s set it to the repository name airline_financials:
WORKDIR /airline_financials

# If your code lives in the same directory as the Dockerfile, copy all your app files from your server into the container, including streamlit_app.py, requirements.txt, etc, by replacing the git clone line with:
COPY . .

# Install your app’s Python dependencies from the cloned requirements.txt in the container:
RUN pip install -r requirements.txt

# The EXPOSE instruction informs Docker that the container listens on the specified network ports at runtime. Your container needs to listen to Streamlit’s (default) port 8501:
EXPOSE 8080

# The HEALTHCHECK instruction tells Docker how to test a container to check that it is still working. Your container needs to listen to Streamlit’s (default) port 8501:
HEALTHCHECK CMD curl --fail http://localhost:8080/_stcore/health

# An ENTRYPOINT allows you to configure a container that will run as an executable. Here, it also contains the entire streamlit run command for your app, so you don’t have to call it from the command line:
ENTRYPOINT ["streamlit", "run", "airline_comparison.py", "--server.port=8080", "--server.address=0.0.0.0"]