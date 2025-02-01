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
    results = service.users().messages().list(userId='me', labelIds=['INBOX'], q="is:unread category:primary").execute()
    messages = results.get('messages', [])
    emails = []
    if not messages:
        print("No unread messages found.")
    else:
        for message in messages[:5]:
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

def mark_as_read(service, email_id):
    """Mark an email as read by removing the UNREAD label."""
    try:
        service.users().messages().modify(
            userId="me",
            id=email_id,
            body={"removeLabelIds": ["UNREAD"]}
        ).execute()
    except Exception as e:
        print(f"Error marking email as read: {e}")

# Function to extract and respond
def extract_and_respond(email_data):
    """Extract sender's email, subject, and content from email data, 
    and generate a response using the Gemini API."""
    
    model = ChatGoogleGenerativeAI(model="gemini-2.0-flash-exp", api_key="AIzaSyDlGuiJOqQePVsQEu5gWiftb74RDGvcq-c")
    extraction_prompt = f"""
    The following is raw email data. Extract the following details:
    - Sender's Email
    - Email Subject
    - Email Content (prefer Plain Text if available, otherwise use HTML Part give me all the content in the email)

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
    
    if "Sender" in details and "Content" in details and "Subject" in details:
        response_prompt = f"""
        Write a polite and professional response to the following email also add my name : muhammad uzair , also select a creative subject according to the response that u have created and  your response should not include this line = (Okay, here's a polite and professional response you can use,incorporating your name:)  and i am a receiver so subject should me according to the response:
        - Sender: {details['Sender']}
        - Subject: {details['Subject']}
        - Content: {details['Content']}
        """
        response = model.predict(response_prompt)
    else:
        response = "Could not extract all necessary details from the email data."
    
    return details, response

def check_if_responded(service, email_id):
    """Check if the email has been responded to by looking at the thread ID."""
    # Get the email message details
    msg = service.users().messages().get(userId='me', id=email_id).execute()
    
    # Get the thread ID
    thread_id = msg['threadId']
    
    # Get all messages in the thread
    thread = service.users().threads().get(userId='me', id=thread_id).execute()
    
    # Check if the thread has more than one message (i.e., it's been replied to)
    if len(thread['messages']) > 1:
        return True
    else:
        return False

# Function to send email response
def send_email_response(service, sender_email, subject, response_content):
    """Send a response email to the sender.""" 
    
    message = MIMEMultipart()
    message["From"] = "your_email@example.com"  # Replace with your email
    message["To"] = sender_email
    message["Subject"] = f"Re: {subject}"
    message.attach(MIMEText(response_content, "plain"))

    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

    try:
        service.users().messages().send(userId="me", body={"raw": raw_message}).execute()
        return True
    except Exception as e:
        return False


# Streamlit UI
st.title("Gmail Assistant")

# Authenticate Gmail
service = authenticate_gmail()
# Initialize edited_response in session_state
if 'edited_response' not in st.session_state:
    st.session_state['edited_response'] = ""

# Fetch unread emails
emails = list_emails(service)

# Responded emails list
responded_emails = []

if emails:
    st.sidebar.header("Emails")

    # Sidebar: Unread Emails
    st.sidebar.subheader("Unread Emails")
    for idx, email in enumerate(emails, 1):
        st.sidebar.text(f"{idx}. {email['subject']} (From: {email['sender']})")

    # Sidebar: Responded Emails

    # Right sidebar (Responded Emails)
    st.write("### Select an email to view details")
    email_select = st.selectbox("Select an email", [""] + [f"{email['subject']} (From: {email['sender']})" for email in emails])

    if email_select:
        selected_email = emails[[f"{email['subject']} (From: {email['sender']})" for email in emails].index(email_select)]

        # Extract details and generate the initial response
        details, response = extract_and_respond(selected_email['message'])

        st.write("### Email Details:")
        st.write(f"**Sender**: {details['Sender']}")
        st.write(f"**Subject**: {details['Subject']}")
        st.write(f"**Content**: {details['Content']}")

        # Initialize the response in session state
        if 'edited_response' not in st.session_state or not st.session_state['edited_response']:
            st.session_state['edited_response'] = response

        # Display the editable text area
        st.write("### Generated Response:")
        st.session_state['edited_response'] = st.text_area("Edit the response", st.session_state['edited_response'], height=200)

        # Send email response button
        if st.button("Send Response"):
            success = send_email_response(service, details["Sender"], details["Subject"], st.session_state['edited_response'])
            if success:
                st.success(f"Response sent to {details['Sender']}")
                # Mark the email as read
                mark_as_read(service, selected_email['id'])
                # Add this email to responded list
                responded_emails.append({'subject': details['Subject'], 'sender': details['Sender']})
                st.sidebar.subheader("Responded Emails")
                if responded_emails:
                        for idx, email in enumerate(responded_emails, 1):
                            st.sidebar.text(f"{idx}. {email['subject']} (From: {email['sender']})")
                else:
                        st.sidebar.text("No responded emails yet.")


else:
    st.write("No unread emails found.")
