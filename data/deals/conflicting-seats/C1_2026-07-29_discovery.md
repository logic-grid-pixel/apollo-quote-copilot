# Call transcript

**Call ID:** C1
**Date:** 2026-07-29
**Type:** Discovery
**Duration:** 31 min
**Account:** Postman (postman.com)
**Participants:**
- Alex Chen, Account Executive
- Priya Raghunathan, VP Engineering, Postman

> Synthetic transcript for a product demo. All people are fictional; this is not a real conversation with Postman.

---

[00:00:07] Alex Chen: — oh, there you are. Hi Priya.

[00:00:16] Priya Raghunathan: Hi, sorry, Zoom wanted to update itself. Classic.

[00:00:29] Alex Chen: [laughs] It always picks the moment. No worries at all. How's your week going?

[00:00:46] Priya Raghunathan: It's — it's a week. It's been a week. We had a bit of an incident on Monday so I'm still sort of digging out from that.

[00:01:09] Alex Chen: Oh no. Anything customer-facing?

[00:01:18] Priya Raghunathan: Yeah, unfortunately. Not huge, about forty minutes of degraded, um, degraded API responses for a chunk of users. But you know how it is, forty minutes feels like forty hours when you're in it.

[00:01:58] Alex Chen: Oof. Yeah. What was it, if you don't mind me asking?

[00:02:11] Priya Raghunathan: Honestly, a config change that went out without, uh, without the right review. Which is partly why I took this call, to be fair. The postmortem basically said our change process is too manual and too dependent on who happens to be around.

[00:03:00] Alex Chen: That's — yeah. That's the most common story we hear, honestly. It's never the big architectural thing, it's the one YAML file someone edited at 5pm.

[00:03:29] Priya Raghunathan: [laughs] It was literally a YAML file.

[00:03:35] Alex Chen: It's always a YAML file.

[00:03:42] Priya Raghunathan: It's always a YAML file.

[00:03:49] Alex Chen: Okay, well, I'm sorry about that, and I hope the postmortem's at least going somewhere useful. Um — actually, before we dive in, I think we met? Or at least we were in the same room. Were you at PlatformCon in June? I feel like I saw your name on a panel.

[00:04:38] Priya Raghunathan: Oh! Yes, I was on the, um, the developer experience panel. The one that ran really long.

[00:04:57] Alex Chen: That's the one! I was in the back. The moderator kept trying to wrap and nobody would stop talking.

[00:05:17] Priya Raghunathan: [laughs] That was mostly the guy on the end. He had a lot of thoughts about monorepos.

[00:05:33] Alex Chen: He did have a lot of thoughts. I actually thought your point about, um, paved roads being a product and not a project was the best thing anyone said all day.

[00:06:02] Priya Raghunathan: Oh, thank you. Yeah, I believe that pretty strongly. Did you go to the — the dinner thing after? At the rooftop place?

[00:06:25] Alex Chen: I tried. The line was insane. I ended up getting tacos with two people from our team.

[00:06:45] Priya Raghunathan: Honestly, probably the better choice. The rooftop was so loud you couldn't talk to anyone.

[00:07:01] Alex Chen: [laughs] Okay, good, I feel better about the tacos. Anyway — so, um, let's talk about you. What made you want to take a call?

[00:07:27] Priya Raghunathan: So, partly the incident, like I said. But really this has been on the list for a while. We have a lot of, um, tribal knowledge in how changes get made and environments get set up. And as we've grown that's just not scaling.

[00:08:16] Alex Chen: What does "a lot of tribal knowledge" look like day to day?

[00:08:29] Priya Raghunathan: It looks like — okay, if you're a new engineer and you want to spin up an environment, you go ask someone. And that someone depends on which team you're on. And they each do it slightly differently.

[00:09:08] Alex Chen: Right.

[00:09:12] Priya Raghunathan: And then when something goes wrong, like on Monday, it's hard to even figure out what the process was supposed to be.

[00:09:31] Alex Chen: Got it. And you want — um, is the goal more standardisation, more self-service, more guardrails? All three?

[00:09:54] Priya Raghunathan: Probably all three, but I'd say guardrails first. After Monday, guardrails first.

[00:10:11] Alex Chen: Makes sense. Um, who'd be using it? Like, which part of the org?

[00:10:27] Priya Raghunathan: So it would be the engineering org that reports up to me. I have to check, honestly, the exact number, because we've had some reorgs and I don't want to give you something wrong. But it's roughly 50 engineers who'd need access. Somewhere around there.

[00:11:16] Alex Chen: Roughly 50, okay.

[00:11:22] Priya Raghunathan: Roughly. Don't hold me to it. I need to check internally.

[00:11:35] Alex Chen: No, totally, that's fine for now. Just helps me think about which tier makes sense.

[00:11:52] Priya Raghunathan: Yeah. Um — I think we looked at your pricing page, someone on my team did, and they thought Pro was the right one?

[00:12:11] Alex Chen: For that kind of group, Pro is usually where people land. It's got the approval workflows and the audit history, which, after an incident like Monday's, is probably what you want.

[00:12:44] Priya Raghunathan: Yeah. That's what they said. Okay.

[00:12:54] Alex Chen: Can I ask what else you're looking at? I assume we're not the only ones.

[00:13:07] Priya Raghunathan: No, you're not. We're evaluating two other vendors. I'd rather not say who yet, just because it's early, but, um, two others.

[00:13:33] Alex Chen: Totally fair. Is there anything about them that's standing out, either good or bad? Just so I know what I'm up against.

[00:13:56] Priya Raghunathan: One of them has a really nice UI, honestly. The other one is, um, more flexible but it felt like a lot of setup. I don't have a strong opinion yet. I need to get my team's input.

[00:14:35] Alex Chen: That's useful, thank you. We tend to land somewhere in between — it's opinionated out of the box but you can go pretty deep if you want.

[00:15:01] Priya Raghunathan: Okay. That might be the right balance. I'd have to see it.

[00:15:14] Alex Chen: Happy to do a proper technical session with whoever on your team would be, um, the most sceptical.

[00:15:34] Priya Raghunathan: [laughs] That's Tom. He's a staff engineer, he's going to have a lot of questions about integrations and APIs.

[00:15:53] Alex Chen: Perfect. That's exactly who I want.

[00:16:03] Priya Raghunathan: He'll ask about rate limits. He always asks about rate limits.

[00:16:13] Alex Chen: [laughs] We'll be ready.

[00:16:19] Priya Raghunathan: Good.

[00:16:26] Alex Chen: So, um, timeline. Is there a date you're working toward, or is it more open-ended?

[00:16:42] Priya Raghunathan: There is. So our fiscal quarter starts October 1, and I'd like to have this in place for the start of that quarter. That's when a lot of the new planning kicks in, and honestly it's cleaner budget-wise to start something at the top of a quarter.

[00:17:28] Alex Chen: October 1 start. Okay. That's pretty doable if we get moving in the next few weeks.

[00:17:44] Priya Raghunathan: Yeah. I mean, that's the goal. I have to check with finance that it lines up, but I think it does.

[00:18:04] Alex Chen: And on budget — is this something you have already, or something you'd need to go get?

[00:18:20] Priya Raghunathan: I think I have it. I need to check internally how it's allocated. It's a tooling line, I think. I'm fairly sure.

[00:18:43] Alex Chen: Okay. And you'd be the one signing?

[00:18:53] Priya Raghunathan: For something this size, I believe I can sign. Again, I'd need to double-check the threshold. Sorry, I'm saying "check" a lot.

[00:19:16] Alex Chen: [laughs] No, it's the first call, that's totally normal. I'd rather you check than guess.

[00:19:32] Priya Raghunathan: Thank you.

[00:19:39] Alex Chen: Um, can I show you a couple of things? Just so you have a picture for when you're talking to Tom and the others.

[00:19:55] Priya Raghunathan: Sure, yeah.

[00:20:01] Alex Chen: Okay, sharing. [pause] You should see a dashboard.

[00:20:14] Priya Raghunathan: I see it.

[00:20:21] Alex Chen: So this is the change approval flow. If you think about Monday — someone edits a config, it goes through here. You define the rules. For example, anything touching production API gateway config needs two approvers, one of whom is on-call.

[00:21:10] Priya Raghunathan: And that's enforced? Like, they can't just skip it?

[00:21:20] Alex Chen: Enforced. The only bypass is a break-glass, which is logged and pages whoever you choose.

[00:21:39] Priya Raghunathan: Oh, that's good. That would have — yeah. That would have caught it.

[00:21:52] Alex Chen: And then here's the audit view. You can go back and see who approved what, when.

[00:22:09] Priya Raghunathan: Can I filter by service?

[00:22:15] Alex Chen: By service, by team, by person, by time range.

[00:22:25] Priya Raghunathan: Okay. [pause] Okay, that's — yeah. That's nice. I'd want Tom to see this.

[00:22:41] Alex Chen: Definitely. [inaudible] — sorry, my dog's barking. Give me one second.

[00:22:58] Priya Raghunathan: [laughs] No worries.

[00:23:14] Alex Chen: Sorry. Delivery guy. She takes it very personally.

[00:23:24] Priya Raghunathan: Mine does the same. What kind?

[00:23:30] Alex Chen: Corgi. Very loud for her size.

[00:23:37] Priya Raghunathan: Oh, they're the loudest. We have a beagle, so. I understand.

[00:23:50] Alex Chen: [laughs] Okay. Um, where was I — so, the other thing is self-service environments, which we can go deep on with Tom, but basically your team defines templates and engineers pick from a catalog.

[00:24:29] Priya Raghunathan: Right. That's the tribal knowledge problem.

[00:24:36] Alex Chen: Exactly. It takes the "go ask someone" out of it.

[00:24:49] Priya Raghunathan: Yeah. Okay. Um — I have to say, I'm interested. I'd like Tom to kick the tires.

[00:25:05] Alex Chen: Great. Let me stop sharing. [pause] Okay. So, um, a couple of quick things before we wrap. SSO — what are you on?

[00:25:31] Priya Raghunathan: Okta. And SSO is — yeah, Tom will tell you, it's non-negotiable. We'll go into that.

[00:25:51] Alex Chen: Noted. And term — are you thinking one year, multi-year?

[00:26:07] Priya Raghunathan: I don't know yet. I need to talk to finance. Can we come back to that?

[00:26:20] Alex Chen: Of course.

[00:26:23] Priya Raghunathan: Honestly, all the commercial stuff I'd rather do once I've checked internally. I don't want to give you numbers and then walk them back.

[00:26:46] Alex Chen: Totally. That's fine. Let's do technical next, and commercials once you've had a chance to check.

[00:27:06] Priya Raghunathan: Perfect.

[00:27:09] Alex Chen: Um — anything else on the incident side I should know? Like, is there a timeline for the postmortem actions that this is part of?

[00:27:32] Priya Raghunathan: Sort of. The action item is literally "evaluate change management tooling", owner me, which is — yeah. So this is me doing my action item.

[00:28:01] Alex Chen: [laughs] I'm honoured to be an action item.

[00:28:08] Priya Raghunathan: [laughs] You should be. Very few vendors make it onto a postmortem.

[00:28:21] Alex Chen: Okay, so, next step — can I get some time with you and Tom in the next couple of weeks?

[00:28:37] Priya Raghunathan: Yes. Let me check his calendar, he's — I think he's out part of next week. Mid-August probably.

[00:28:57] Alex Chen: Works for me. I'll send some options.

[00:29:07] Priya Raghunathan: Great. And, um, send me whatever you have on SSO and the API, I'll forward it to Tom so he's prepared. He likes to be prepared.

[00:29:29] Alex Chen: Will do.

[00:29:33] Priya Raghunathan: And — oh, are you going to the conference in the spring? The one in Austin?

[00:29:46] Alex Chen: I think so, if they let me.

[00:29:52] Priya Raghunathan: We should get tacos. Skip the rooftop.

[00:29:59] Alex Chen: [laughs] Deal. Skip the rooftop.

[00:30:05] Priya Raghunathan: Okay. Thanks, Alex.

[00:30:12] Alex Chen: Thank you, Priya. Good luck with the postmortem.

[00:30:18] Priya Raghunathan: Thanks. I'll need it. Bye.

[00:30:25] [Priya Raghunathan left the call]
