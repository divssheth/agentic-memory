---
name: international-booking
description: "Step-by-step procedure for booking international business travel. Use when employee requests travel to a different country. Includes visa, insurance, and advance booking requirements."
---

# International Booking Procedure

Follow these steps when booking travel to a different country:

1. **Check preferences**: Query semantic memory for airline, hotel, and seat preferences
2. **Check history**: Recall past international trips. Check for visa-related events or issues
3. **Verify budget**: Use `read_skill_resource("international-booking", "budget-limits")` to get budget limits. International trips often exceed domestic limits — flag and escalate if needed
4. **Travel insurance**: International trips REQUIRE travel insurance per company policy. Remind the user and include in the plan
5. **Advance booking**: International trips require 14-day advance booking per company policy. Check the requested dates and warn if too close
6. **Visa check**: Ask if the user has a valid visa for the destination country. Use `read_skill_resource("international-booking", "visa-checklist")` for requirements. Check episodic memory for past visits (which implies prior visa)
7. **Recommend options**: Prefer direct flights for international routes when within budget
8. **Explain reasoning**: Include policy requirements in your explanation
9. **Confirm**: Summarize the complete plan including insurance and visa status
