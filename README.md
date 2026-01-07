# Human Chatbot using AWS Bedrock

## Overview

This project demonstrates my ability to design and implement an end-to-end AI inference workflow using **AWS Bedrock** for real-world usage. While I used **Claude AI** as a coding assistant, the complete **system architecture, workflow, and integration design were planned and implemented solely by me**.

The system acts as a **human-like chatbot** that responds to users on **Telegram using my/admin real account**, not a traditional bot API. Conceptually, it can be compared to a program that replies to friends or family on platforms like WhatsApp using a real account instead of an official bot.

GitHub Repository:
[https://github.com/arunjangir/telegram-chatting-partner.git](https://github.com/arunjangir/telegram-chatting-partner.git)

---

## Key Features

* Responds to users with **natural text conversations**
* Can **send images** when requested by the user
* Can **send voice messages** dynamically
* Uses **Cohere model on AWS Bedrock** with built-in **function calling** capability
* Automatically triggers specific functions (image or voice response) based on user intent

---

## Architecture & Workflow

1. User sends a message on Telegram
2. Message is captured and processed by the backend service
3. Request is forwarded to **AWS Bedrock (Cohere model)**
4. The model analyzes intent and decides:

   * Text response
   * Image generation
   * Voice message generation
5. Function calls are executed accordingly
6. Response is delivered back to the user via Telegram

This approach closely simulates **human-like conversational behavior** rather than a rule-based chatbot.

---

## Technologies Used

* **AWS Bedrock** (Cohere model)
* **Telegram API**
* **Python / Backend Logic**
* **Function Calling (LLM-driven)**
* **AI-assisted development (Claude & ChatGPT)**

---

## Purpose of This Project

* To showcase my ability to:

  * Design AI-driven workflows
  * Integrate multiple tools and platforms
  * Use AWS Bedrock for production-style inference
* To demonstrate practical understanding of **LLM orchestration and function calling**
* To highlight hands-on experience beyond basic chatbot implementations

---

## Disclaimer

This project is built strictly for **learning and demonstration purposes** and is not intended to violate the terms of any messaging platform.

---

## Author

**Arun Jangir**
Cloud & DevOps Engineer
