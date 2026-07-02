---
name: domestic-booking
description: "Step-by-step procedure for booking domestic (same-country) business travel. Use when employee requests a flight, hotel, or trip within their home country."
---

# Domestic Booking Procedure

Follow these steps when booking travel within the same country:

1. **Check preferences**: Query semantic memory for airline, hotel, and seat preferences
2. **Check history**: Recall past trips to the same city. If the user has been there before, reference their experience (hotel rating, what worked/didn't)
3. **Verify budget**: Use `read_skill_resource("domestic-booking", "budget-limits")` to get budget limits by employee level. Check the booking amount against the limit.
4. **Recommend options**: Use preferences and history to suggest specific flights/hotels
5. **Explain reasoning**: Tell the user WHY you're recommending each option
6. **Confirm**: Summarize the complete plan and get user approval before booking
