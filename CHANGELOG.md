<div align="center">

# FeedbackBot Changelog  
Compact record of updates, in reverse chronological order.

</div>

> [!NOTE]  
> Versions follow semantic versioning (`vX.Y.Z`) — `X`: major updates, `Y`: features & improvements, `Z`: patches or internal changes.

---

## v1

<details>
<summary>v1.0.1 – Improved Logging & Reply Handling</summary>

- Switched from `forward()` to explicit `send_*()` methods for accurate media logging  
- Appended user ID in logs to enable stable admin replies without `forward_origin`  
- Admin reply handler now extracts user ID using regex for higher reliability  
- General stability and formatting improvements in log forwarding

</details>

<details>
<summary>v1.0.0 – Initial Release</summary>

- First public version of FeedbackBot  
- All planned features completed and functional  
- Refer to [README](./README.md) for full feature list

</details>
