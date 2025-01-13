import os
import pickle
import base64
import streamlit as st
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from langchain.chains import ConversationChain
from langchain_google_genai import ChatGoogleGenerativeAI

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

# Authentication function
def authenticate_gmail():
    """Authenticate Gmail API and manage credentials."""
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    service = build('gmail', 'v1', credentials=creds)
    return service

# Function to list emails
def list_emails(service):
    """Fetch and display top 10 unread emails."""
    results = service.users().messages().list(userId='me', labelIds=['INBOX'], q="is:unread").execute()
    messages = results.get('messages', [])
    emails = []
    if not messages:
        print("No unread messages found.")
    else:
        for message in messages[:10]:
            msg = service.users().messages().get(userId='me', id=message['id']).execute()
            headers = msg['payload']['headers']
            subject = next((header['value'] for header in headers if header['name'] == 'Subject'), "No Subject")
            sender = next((header['value'] for header in headers if header['name'] == 'From'), "Unknown Sender")
            emails.append({'id': message['id'], 'subject': subject, 'sender': sender, 'message': msg})
    return emails

# Function to generate a response using Langchain
def generate_response(email_content):
    """Generate a response using Langchain."""
    model = ChatGoogleGenerativeAI(model="gemini-2.0-flash-exp", api_key="AIzaSyDlGuiJOqQePVsQEu5gWiftb74RDGvcq-c")  # Replace with your API key
    conversation = ConversationChain(llm=model)
    response = conversation.invoke(input=email_content)
    return response

# Function to extract email details
def extract_email_details(email_data):
    """Extract sender's email, subject, and content from email data."""
    model = ChatGoogleGenerativeAI(model="gemini-2.0-flash-exp", api_key="AIzaSyDlGuiJOqQePVsQEu5gWiftb74RDGvcq-c")
    extraction_prompt = f"""
    The following is raw email data. Extract the following details:
    - Sender's Email
    - Email Subject
    - Email Content (prefer Plain Text if available, otherwise use HTML Part)

    Email data:
    {email_data}

    Provide the extracted information in this format:
    Sender: <sender_email>
    Subject: <email_subject>
    Content: <email_content>
    """
    
    extracted_response = model.predict(extraction_prompt)
    
    details = {}
    for line in extracted_response.split("\n"):
        if line.startswith("Sender:"):
            details["Sender"] = line.split("Sender:")[1].strip()
        elif line.startswith("Subject:"):
            details["Subject"] = line.split("Subject:")[1].strip()
        elif line.startswith("Content:"):
            details["Content"] = line.split("Content:")[1].strip()

    return details

# Function to generate email response
def generate_email_response(details):
    """Generate a polite and professional response to the extracted email details."""
    if "Sender" in details and "Content" in details and "Subject" in details:
        response_prompt = f"""
        Write a polite and professional response to the following email also add my name: muhammad uzair:
        - Sender: {details['Sender']}
        - Subject: {details['Subject']}
        - Content: {details['Content']}
        """
        
        model = ChatGoogleGenerativeAI(model="gemini-2.0-flash-exp", api_key="AIzaSyDlGuiJOqQePVsQEu5gWiftb74RDGvcq-c")
        response = model.predict(response_prompt)
    else:
        response = "Could not extract all necessary details from the email data."
    
    return response
# Function to send email response
def send_email_response(service, sender_email, subject, response_content):
    """Send a response email to the sender."""
    message = MIMEMultipart()
    message["From"] = "uzairyasin395@gmail.com"    # Replace with your email
    message["To"] = sender_email
    message["Subject"] = f"Re: {subject}"
    message.attach(MIMEText(response_content, "plain"))

    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

    try:
        service.users().messages().send(userId="me", body={"raw": raw_message}).execute()
        st.success(f"Response sent to {sender_email}")
        return True
    except Exception as e:
        st.error(f"Failed to send response: {str(e)}")
        return False

# Streamlit UI
st.title("Gmail Assistant")

# Authenticate Gmail
service = authenticate_gmail()

# Fetch unread emails
emails = list_emails(service)

if emails:
    # Display list of unread emails
    st.write("### Unread Emails")
    email_select = st.selectbox("Select an email", [f"{email['subject']} (From: {email['sender']})" for email in emails])
    
    if email_select:
        selected_email = emails[[f"{email['subject']} (From: {email['sender']})" for email in emails].index(email_select)]
        
        # Extract details and display email information
        details = extract_email_details(selected_email['message'])
        
        # Show email details
        st.write(f"**Subject:** {details.get('Subject', 'N/A')}")
        st.write(f"**Sender:** {details.get('Sender', 'N/A')}")
        st.write(f"**Content:** {details.get('Content', 'N/A')}")
        
        # Generate response
        if st.button("Generate Response"):
            response = generate_email_response(details)
            st.write("### Generated Response:")
            st.write(response)

        # Send email response
        if 'response' in locals() and st.button("Send Response"):
            success = send_email_response(service, details["Sender"], details["Subject"], response)
            if success:
                st.success(f"Response sent to {details['Sender']}")
            else:
                st.error("Failed to send the response.")
else:
    st.write("No unread emails found.")
