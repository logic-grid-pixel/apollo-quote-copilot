# Call transcript

**Call ID:** C2
**Date:** 2026-08-14
**Type:** Technical evaluation
**Duration:** 52 min
**Account:** Postman (postman.com)
**Participants:**
- Alex Chen, Account Executive
- Priya Raghunathan, VP Engineering, Postman
- Tom Abara, Staff Engineer, Postman

> Synthetic transcript for a product demo. All people are fictional; this is not a real conversation with Postman.

---

[00:00:17] Alex Chen: Hi both! Priya, good to see you again. And Tom, nice to meet you.

[00:00:39] Tom Abara: Hey. Nice to meet you.

[00:00:50] Priya Raghunathan: Hi Alex. Tom's read everything you sent, so, um, brace yourself.

[00:01:17] Alex Chen: [laughs] Great. That's the best kind of call. Tom, do you want to just drive? You tell me what you want to see and I'll show it.

[00:01:56] Tom Abara: Sure. I have a list. It's, uh, it's not a short list.

[00:02:18] Alex Chen: I love a list.

[00:02:29] Tom Abara: Okay. So, SSO first, because if that doesn't work, nothing else matters. Then SCIM, then data residency, then the API, then how the change approval thing actually hooks into our deploy pipeline. Probably in that order.

[00:03:46] Alex Chen: Perfect. Let's go. SSO — you're on Okta, Priya mentioned.

[00:04:08] Tom Abara: Okta, SAML. And I want to be really clear, SSO is a hard requirement. We don't allow any tool that has its own username and password. Security won't approve it, full stop.

[00:05:09] Alex Chen: Understood. We support SAML 2.0 and OIDC. With Okta you can use either, most customers use SAML. And you can enforce SSO-only, so local passwords are disabled entirely for your tenant.

[00:06:21] Tom Abara: Including for admins? Some tools let admins bypass.

[00:06:37] Alex Chen: Including for admins. There's one break-glass account, which you control, and it's, um, it's MFA-enforced and every login is logged and alerts.

[00:07:27] Tom Abara: Can we turn that off? The break-glass?

[00:07:44] Alex Chen: You can disable it, yes. Some customers do. We'd just want you to know that if Okta goes down, you'd be locked out.

[00:08:22] Tom Abara: That's — okay, fine, that's a reasonable trade-off. We'll decide internally.

[00:08:44] Priya Raghunathan: Write that down, Tom, security will ask.

[00:08:55] Tom Abara: Writing it down.

[00:09:06] Alex Chen: Um, SCIM — we support SCIM 2.0. Provisioning, deprovisioning, group sync. When someone leaves and Okta deactivates them, they're out of our side within, um, a couple of minutes.

[00:10:13] Tom Abara: Push or pull?

[00:10:24] Alex Chen: Okta pushes to us.

[00:10:35] Tom Abara: Okay. And groups map to roles?

[00:10:46] Alex Chen: Groups map to roles, yes. You configure the mapping once.

[00:11:08] Tom Abara: Nested groups?

[00:11:19] Alex Chen: Um — flattened. So if you have nested groups in Okta, we see the flattened membership. We don't model the hierarchy.

[00:12:03] Tom Abara: Hm. Okay. That's probably fine. We don't nest much.

[00:12:25] Priya Raghunathan: We nest a little.

[00:12:31] Tom Abara: We nest a little, but it's fine.

[00:12:42] Alex Chen: [laughs] Okay.

[00:12:53] Tom Abara: Data residency. Where does our data live?

[00:13:09] Alex Chen: Default is US, AWS us-east. We also have an EU region, Frankfurt. You pick at tenant creation.

[00:13:53] Tom Abara: Can we split? Like some data in the EU and some in the US?

[00:14:15] Alex Chen: Not within one tenant. You'd need two tenants for that, which is an Enterprise thing.

[00:14:43] Priya Raghunathan: We don't need that. We're fine with US.

[00:15:00] Tom Abara: Are we? What about the, uh, the Bangalore folks?

[00:15:16] Priya Raghunathan: It's config metadata, not customer data. Legal already said US is fine for that.

[00:15:44] Tom Abara: Okay. As long as legal said.

[00:15:55] Alex Chen: And just so you have it — the data we store is config, templates, audit logs, approval records. We don't store your application data or secrets. Secrets stay in your vault, we reference them.

[00:17:01] Tom Abara: Which vault?

[00:17:06] Alex Chen: HashiCorp Vault, AWS Secrets Manager, GCP Secret Manager. Those three natively.

[00:17:40] Tom Abara: We're on Vault. Good.

[00:17:51] Alex Chen: Okay. The API.

[00:18:02] Tom Abara: The API. Okay. So. Rate limits.

[00:18:18] Priya Raghunathan: [laughs] I told you.

[00:18:24] Alex Chen: [laughs] She did tell me.

[00:18:35] Tom Abara: I'm predictable. Look, we got burned by this. Our last tool had a rate limit that was fine on paper and then our CI would fire off a burst of calls on a big merge and we'd get throttled, and the builds would just fail. So what are the actual limits, and are they per token, per tenant, per IP?

[00:20:14] Alex Chen: So on Pro, it's per tenant, and it's, um, a thousand requests per minute sustained, with burst up to three thousand for short windows.

[00:21:04] Tom Abara: Per tenant. So if I have ten pipelines hitting it at once, they share the thousand.

[00:21:31] Alex Chen: They share it, yes.

[00:21:42] Tom Abara: Hm. That's — okay, what happens when you hit it? Hard 429, or do you queue?

[00:22:10] Alex Chen: 429 with a Retry-After header. Our SDK handles backoff automatically.

[00:22:38] Tom Abara: We wouldn't use the SDK, we'd call it directly from our pipeline scripts.

[00:23:00] Alex Chen: Then you'd want to honour the Retry-After. It's standard.

[00:23:16] Tom Abara: Right, but my question is — can we get the limit raised? Because on a big release day we could plausibly spike past three thousand in a minute. Not sustained, but for a minute or two.

[00:24:17] Alex Chen: It can be raised. On Enterprise it's higher by default, on Pro we can raise it on request, um, I'd need to check what the ceiling is without going to Enterprise. Let me take that one back.

[00:25:18] Tom Abara: Yeah. I'd want that in writing before we commit. Honestly that's the thing that would make me say no.

[00:25:51] Priya Raghunathan: Is it really that big, Tom?

[00:26:02] Tom Abara: It's that big. If our release pipeline fails because a third-party tool throttled us, that's an incident. We just had one of those.

[00:26:40] Priya Raghunathan: Okay. Fair.

[00:26:46] Alex Chen: Understood. I'll get you a written answer on the ceiling for Pro, and what the process is to raise it. Um, is there a number you'd want to see, so I ask the right question?

[00:27:36] Tom Abara: Sustained at least double what you said, and burst — I don't know, let me look at our actual traffic and I'll send you something.

[00:28:14] Alex Chen: Perfect, that's really helpful. Do you want to see the API docs quickly?

[00:28:36] Tom Abara: I've read them. They're good, actually. The OpenAPI spec is complete, which, you'd be surprised.

[00:29:09] Alex Chen: [laughs] Thank you, I'll pass that on to the docs team, they'll be thrilled.

[00:29:32] Tom Abara: One thing — webhooks. Are they signed?

[00:29:48] Alex Chen: HMAC signed, yeah. And you can rotate the secret without downtime, there's an overlap window.

[00:30:21] Tom Abara: Good. And retries on webhooks?

[00:30:32] Alex Chen: Exponential backoff, up to twenty-four hours, then it goes to a dead-letter view in the UI.

[00:31:05] Tom Abara: Okay. That's solid.

[00:31:16] Alex Chen: Okay. Last thing on your list — the pipeline integration. Let me share. [pause] Can you see it?

[00:31:49] Tom Abara: Yep.

[00:32:01] Alex Chen: So the way most people integrate is a step in the pipeline that calls our approval check. If the change needs approval, the step blocks until it's approved or times out.

[00:32:56] Tom Abara: Blocks how? Polling?

[00:33:07] Alex Chen: Either polling, or you can use the webhook to resume. We have plugins for GitHub Actions, GitLab, Jenkins, Buildkite.

[00:33:45] Tom Abara: We're on GitHub Actions. And the action is open source?

[00:34:02] Alex Chen: Yes, it's on GitHub.

[00:34:13] Tom Abara: Okay, I'll look at it. What if your service is down? Does our pipeline block forever?

[00:34:41] Alex Chen: Configurable. You choose fail-open or fail-closed per rule. Most people fail-closed for production and fail-open for dev.

[00:35:25] Tom Abara: Good, that's the right answer. That was kind of a trick question.

[00:35:41] Alex Chen: [laughs] I figured.

[00:35:52] Priya Raghunathan: He does that.

[00:36:03] Tom Abara: Sorry.

[00:36:09] Alex Chen: No, it's good, I'd rather you ask now.

[00:36:25] Tom Abara: Um — one more on this. Can the approval rules be defined as code? I don't want people clicking around in a UI to change who approves production.

[00:37:10] Alex Chen: Yes. Rules can be defined in a repo, synced by us. And you can lock the UI so rules are code-only.

[00:37:48] Tom Abara: Oh, that's nice. Okay.

[00:37:59] Priya Raghunathan: That's the thing that would have caught Monday. Well — the Monday from a few weeks ago.

[00:38:27] Tom Abara: [laughs] The Monday.

[00:38:38] Alex Chen: How did the postmortem land, by the way?

[00:38:54] Priya Raghunathan: It landed. We have actions. This is one of them, as I said.

[00:39:17] Alex Chen: Still honoured.

[00:39:22] Priya Raghunathan: [laughs]

[00:39:33] Alex Chen: Um, okay, let me stop sharing. [pause] Tom, anything else technical?

[00:40:01] Tom Abara: Uh — audit log export. Can it go to our SIEM?

[00:40:23] Alex Chen: Yes, we stream to Splunk, Datadog, or any S3 bucket. JSON.

[00:40:50] Tom Abara: Datadog. Okay. Um, and — actually no, I think that's it. The rate limit thing is the big one.

[00:41:23] Alex Chen: Got it. I'll get you that in writing this week.

[00:41:40] Priya Raghunathan: Can I jump in on one non-technical thing, since I have you both?

[00:41:57] Alex Chen: Of course.

[00:42:02] Priya Raghunathan: Term. I talked to finance, like I said I would. We'd want a two-year term. They like predictability, they don't want to re-budget this every twelve months and get surprised by a price change.

[00:43:03] Alex Chen: Two years, okay. That's great, that's easy for us. Um, do you want to go into pricing now, or —

[00:43:30] Priya Raghunathan: No, not now. Let's do that separately. I just wanted to flag the term so you can think about it.

[00:43:58] Alex Chen: Sounds good. I'll keep that in mind.

[00:44:09] Tom Abara: Sorry — Priya, I have to drop in like five minutes, I have an interview.

[00:44:31] Priya Raghunathan: Oh, yeah, go. We're basically done.

[00:44:42] Alex Chen: Tom, before you go — anything else you need from me besides the rate limit answer?

[00:45:10] Tom Abara: Um. The SOC 2, and a sandbox. Can I get a sandbox to try the GitHub Action against a test repo?

[00:45:43] Alex Chen: Yes, I'll set one up and send you credentials — well, SSO, you'll log in with Okta once we connect it.

[00:46:16] Tom Abara: [laughs] Right, obviously.

[00:46:27] Alex Chen: I'll send the SAML metadata so you can set up the app in Okta.

[00:46:49] Tom Abara: Great. Thanks, Alex. That was actually useful.

[00:47:06] Alex Chen: "Actually useful." I'll take it.

[00:47:17] Tom Abara: [laughs] High praise from me. Okay, bye.

[00:47:33] [Tom Abara left the call]

[00:47:44] Priya Raghunathan: He liked it. That's him liking it.

[00:48:01] Alex Chen: [laughs] Good to know. Um, so, next steps from my side — rate limit answer in writing, sandbox for Tom, SOC 2. And then a commercial conversation with you.

[00:48:56] Priya Raghunathan: Yeah. Let's do that in a couple of weeks. I want to see how Tom's sandbox goes first.

[00:49:24] Alex Chen: Makes sense. And, um, you mentioned the two other vendors last time — is Tom doing the same kind of session with them?

[00:50:02] Priya Raghunathan: He did one last week. The other one's next week.

[00:50:19] Alex Chen: Okay. Anything I should know from the one last week?

[00:50:35] Priya Raghunathan: [laughs] Nice try. I'll just say Tom asked them about rate limits too.

[00:50:57] Alex Chen: [laughs] Fair enough.

[00:51:08] Priya Raghunathan: Okay. Thanks Alex. Talk soon.

[00:51:19] Alex Chen: Thanks Priya. Bye.

[00:51:25] [Priya Raghunathan left the call]
