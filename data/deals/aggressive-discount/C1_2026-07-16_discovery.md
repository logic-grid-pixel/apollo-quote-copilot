# Call transcript

**Call ID:** C1
**Date:** 2026-07-16
**Type:** Discovery
**Duration:** 44 min
**Account:** Snowflake (snowflake.com)
**Participants:**
- Jordan Mwangi, Account Executive
- Ellis Moreau, Director of Infrastructure, Snowflake
- Wen Li, Principal Engineer, Snowflake

> Synthetic transcript for a product demo. All people are fictional; this is not a real conversation with Snowflake.

---

[00:00:16] Jordan Mwangi: Hi Ellis, hi Wen. Thanks for making the time.

[00:00:32] Ellis Moreau: Hi Jordan.

[00:00:38] Wen Li: Hey.

[00:00:43] Jordan Mwangi: So, um, I know we've traded a few emails. I'd love to start by just understanding what you're trying to do, and then I can show you whatever's most relevant. Does that work?

[00:01:31] Ellis Moreau: That works. I'll be upfront with you, though, so we don't waste each other's time. We've been through this before. Not with you, with someone else. And it did not end well.

[00:02:25] Jordan Mwangi: Okay. I appreciate you saying that. Do you mind telling me what happened?

[00:02:47] Ellis Moreau: Sure. We brought in a vendor for something in this space. The first contract was great. Good price, good onboarding, everybody was happy. And then renewal came around and they came back with a number that was, um — what was it, Wen?

[00:04:02] Wen Li: It was a lot. It was a lot more.

[00:04:13] Ellis Moreau: It was a lot more. Like, not a small uplift. They'd figured out that we were locked in, we'd built everything around them, and they priced accordingly. And we ended up ripping it out, which cost us more than just paying would have, honestly. But it was the principle.

[00:05:34] Jordan Mwangi: That's — yeah. I'm sorry. That's a pretty common story and it's a bad one.

[00:06:01] Ellis Moreau: It is. So I'm just telling you now — whatever we do, I care a lot more about what happens at renewal than about what happens on day one. A great first-year price that gets doubled later is worthless to me.

[00:07:05] Jordan Mwangi: That's really clear, and honestly really helpful. We can talk about how we handle that. Um, we do price protection on multi-year deals, so it's something we can build in.

[00:07:59] Ellis Moreau: Good. We'll come back to that. I'm going to hold you to it.

[00:08:15] Jordan Mwangi: Please do.

[00:08:26] Ellis Moreau: Okay. So — context. I run infrastructure. Wen's our principal engineer on the platform side. What we're trying to do is standardise how engineering teams get environments and how changes get approved, because right now it's, um, it's inconsistent.

[00:09:52] Jordan Mwangi: Inconsistent across teams?

[00:10:03] Ellis Moreau: Across teams, and more to the point, across business units. We have three business units that each grew up doing things their own way. And long term, whatever we pick needs to work across all three of them.

[00:11:07] Jordan Mwangi: Okay. All three eventually. But not all at once?

[00:11:29] Ellis Moreau: Not all at once. No. We'd start with one. Mine. And prove it out.

[00:11:56] Jordan Mwangi: Makes sense. Um, and roughly how many people would that first group be?

[00:12:17] Ellis Moreau: [pause] I'm going to be careful here, because I don't want to give you a number and have it end up on a contract before I've checked it.

[00:12:55] Jordan Mwangi: Totally fair.

[00:13:00] Ellis Moreau: But — ballpark — we'd want to start with 200 seats. And grow from there as the other units come on. That's the rough shape.

[00:13:43] Jordan Mwangi: 200 to start, and grow. Okay. And the other units — are they similar size?

[00:14:10] Ellis Moreau: I'm not going to go into that today. We'll get there.

[00:14:27] Jordan Mwangi: No problem.

[00:14:32] Wen Li: Can I jump in with the technical stuff? Because honestly, if it doesn't pass that, we don't need to talk about numbers.

[00:15:04] Jordan Mwangi: Please, go for it.

[00:15:15] Wen Li: So, three things. First, how do you handle multiple business units in one account? Because they have different IdPs right now. Well — two of them are on the same Okta org, one has its own.

[00:16:20] Jordan Mwangi: So on Enterprise we support multiple IdPs per tenant. Each business unit can authenticate against its own identity provider, and you map them into workspaces.

[00:17:13] Wen Li: Workspaces are isolated?

[00:17:24] Jordan Mwangi: Isolated by default. You can share templates across them if you want, but permissions and audit are separate.

[00:18:02] Wen Li: Okay. And is that Enterprise only?

[00:18:18] Jordan Mwangi: Multiple IdPs is Enterprise only, yes.

[00:18:34] Wen Li: Okay. Second — we run a lot of infra ourselves. Some of it's in our own data centres. Does your control plane need to reach into our network?

[00:19:23] Jordan Mwangi: No. We have an agent you run inside your network. It connects outbound to us. We never initiate inbound.

[00:20:00] Wen Li: What does the agent have access to?

[00:20:11] Jordan Mwangi: Whatever you grant it. It runs with a service account you define. We publish the full permission set it needs, and it's scoped per workspace.

[00:20:59] Wen Li: Is it open source?

[00:21:10] Jordan Mwangi: The agent is, yes. You can audit it, build it yourself if you want.

[00:21:32] Wen Li: Okay. That's good. That's actually important. The last vendor's agent was a black box and we had no idea what it was doing.

[00:22:09] Ellis Moreau: Among other problems.

[00:22:15] Wen Li: Among many other problems.

[00:22:26] Jordan Mwangi: [laughs] I'm getting a picture.

[00:22:36] Wen Li: Third thing. Scale. If we did end up across all three units, how does the control plane handle that many workspaces, that many environments? What's your biggest customer?

[00:23:36] Jordan Mwangi: I can't name them, but we have customers running considerably more than what you're describing, across dozens of workspaces. I can put you in touch with one as a reference, under NDA.

[00:24:35] Wen Li: I'd want that. I'd want to talk to an engineer, not a, um, not a marketing reference.

[00:25:02] Jordan Mwangi: Understood. I'll find you an engineer.

[00:25:12] Wen Li: Thanks.

[00:25:23] Ellis Moreau: And I'd want to talk to someone who's renewed. At least once.

[00:25:45] Jordan Mwangi: [laughs] Fair. I'll find someone who's renewed.

[00:26:01] Ellis Moreau: I'm serious.

[00:26:06] Jordan Mwangi: No, I know. I'll do it. Honestly, I think that's a great ask. I'll find a customer on at least their second term.

[00:26:44] Ellis Moreau: Good.

[00:26:55] Jordan Mwangi: Um, can I show you the product for a bit? I think it'll answer some of Wen's questions better than me talking.

[00:27:27] Ellis Moreau: Go ahead.

[00:27:32] Jordan Mwangi: Okay, sharing. [pause] So this is the workspace view. Each of these would be a business unit, in your case. And inside each, templates, approvals, environments.

[00:28:26] Wen Li: Can a template be shared across workspaces but versioned centrally?

[00:28:48] Jordan Mwangi: Yes. You publish from a central workspace and consumers pin a version.

[00:29:15] Wen Li: Hm. And if central pushes a breaking change?

[00:29:31] Jordan Mwangi: Consumers stay on their pinned version until they choose to upgrade. You can see who's on what.

[00:29:58] Wen Li: Okay. That's the right model.

[00:30:08] Jordan Mwangi: And here's the approval policy editor. Policies as code, synced from a repo.

[00:30:35] Wen Li: [inaudible] — sorry, can you zoom? The text is tiny on my screen.

[00:30:57] Jordan Mwangi: Oh, sure. [pause] Better?

[00:31:08] Wen Li: Yeah. Okay, so it's — is that Rego?

[00:31:24] Jordan Mwangi: It's our own DSL, but it compiles to OPA under the hood, and you can bring your own Rego policies if you want.

[00:31:56] Wen Li: Oh, okay. That's interesting. We have a lot of Rego.

[00:32:12] Jordan Mwangi: Then you'd probably want to bring it.

[00:32:23] Wen Li: Yeah.

[00:32:28] Ellis Moreau: Jordan, what's your support model? Because the other thing that went wrong last time was support. It was a queue. You'd file a ticket and hear back in two days.

[00:33:17] Jordan Mwangi: So standard support is business hours, with a next-business-day SLA. Premium support is 24x7 with a one-hour response on P1s and a named support engineer.

[00:34:11] Ellis Moreau: Named as in the same person every time?

[00:34:21] Jordan Mwangi: Same person, plus a backup. They get to know your setup.

[00:34:43] Ellis Moreau: Okay. We'd want that. I'm not doing a queue again.

[00:34:59] Jordan Mwangi: Noted.

[00:35:04] Wen Li: What's the, um, the audit export look like?

[00:35:21] Jordan Mwangi: Stream to your SIEM, or pull via API. JSON, every event.

[00:35:42] Wen Li: Okay. Fine.

[00:35:53] Jordan Mwangi: Let me stop sharing. [pause] Any other technical questions for now?

[00:36:14] Wen Li: Probably a hundred, but I'll send them in writing. It's easier.

[00:36:31] Jordan Mwangi: That's great, honestly, I'd prefer that. I'll get them to our solutions engineer and we'll respond in writing.

[00:37:03] Wen Li: Thanks.

[00:37:08] Jordan Mwangi: Ellis, anything on the — sort of, buying side? Who else would be involved?

[00:37:35] Ellis Moreau: I'm going to hold that for now. I'm the one driving it. Others will get involved when it makes sense.

[00:38:07] Jordan Mwangi: Okay. And — um, timing-wise, is there anything driving urgency?

[00:38:34] Ellis Moreau: Not a hard deadline, no. We want to do it right, not fast. After last time.

[00:39:01] Jordan Mwangi: Understood.

[00:39:07] Ellis Moreau: I'll say this, though. If the renewal story isn't solid, nothing else matters. I'd rather pay more upfront and know what I'm paying for the whole term than get a teaser rate.

[00:40:00] Jordan Mwangi: That's really clear. I'll make sure whatever we propose addresses that head on.

[00:40:27] Ellis Moreau: Good.

[00:40:33] Jordan Mwangi: Okay. So next steps. Wen, you'll send the technical questions. I'll get written answers and line up an engineer reference and a customer who's renewed. And then maybe a second call to go through how rollout would work across the units?

[00:41:43] Ellis Moreau: Yes. A rollout conversation would be useful. I want to see how you'd handle growing into it.

[00:42:15] Jordan Mwangi: Perfect. I'll send some times.

[00:42:26] Ellis Moreau: Okay. Thanks Jordan. This was more useful than I thought it would be, to be honest.

[00:42:53] Jordan Mwangi: [laughs] I'll take that.

[00:43:03] Wen Li: Thanks.

[00:43:09] Jordan Mwangi: Thanks both. Talk soon.

[00:43:20] [Ellis Moreau left the call]

[00:43:25] [Wen Li left the call]
