# OpenAI Agents SDK companion responder — 2026-09-30

Upstream: `openai/openai-agents-python`  
Stars snapshot: 29,786  
Revision inspected: `acdbf289b498e9c10849debb5170aac540ac5828`  
License: MIT

The SDK is integrated only as an optional execution layer:

`CompanionChatRuntime -> OpenAIAgentsResponder -> Runner.run(agent, input=...) -> final_output`

mygpt keeps authority over persona, bounded history, local memory, Book context and supervision policy. The adapter deliberately rejects SDK-owned durable session/conversation state so the same conversation is not persisted twice. A caller may preconfigure tools and handoffs on the Agent.
