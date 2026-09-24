# Call transcript

**Call ID:** C1
**Date:** 2026-08-12
**Type:** Discovery
**Duration:** 34 min
**Account:** Retool (retool.com)
**Participants:**
- Alex Chen, Account Executive
- Dana Whitfield, Director of Platform Engineering, Retool

> Synthetic transcript for a product demo. All people are fictional; this is not a real conversation with Retool.

---

[00:00:13] Alex Chen: Hey Dana, can you hear me okay? I think my audio was doing something weird a second ago.

[00:00:29] Dana Whitfield: Yeah, I've got you. You're a little quiet but it's fine.

[00:00:39] Alex Chen: Let me — okay, how's that, better?

[00:00:49] Dana Whitfield: Much better. Hi.

[00:00:56] Alex Chen: Hi! Thanks for making time. I know you said in the email your week is kind of stacked, so I'll try to keep us honest on time.

[00:01:18] Dana Whitfield: Appreciate it. Yeah, I have a hard stop at the half hour-ish, I've got a planning thing right after that I can't move.

[00:01:41] Alex Chen: Totally. So, um, the way I was thinking we'd use this — I'd love to just hear where you are, what prompted you to reach out, and then I can show you a little bit or not, depending on what's useful. Does that work?

[00:02:20] Dana Whitfield: Yeah, that works. Honestly we've done a fair bit of homework internally already, so I can probably save you some of the discovery questions.

[00:02:43] Alex Chen: Oh, love that. Go for it.

[00:02:50] Dana Whitfield: So, context. I run platform engineering. My team owns the internal developer tooling, the paved-road stuff, CI, environments, all of that. And right now the thing we're trying to solve is that our tooling for this is, frankly, a bit of a patchwork.

[00:03:49] Alex Chen: Patchwork how? Like multiple tools, or —

[00:03:58] Dana Whitfield: Multiple tools and a lot of glue. So there's a pile of scripts that, um, a couple of people on my team wrote years ago and they've kind of become load-bearing, which is never where you want to be. And then we have a legacy vendor for the rest of it, and we're leaving them. That decision's made.

[00:04:57] Alex Chen: Okay. Can I ask what's driving leaving them? Just so I don't walk into the same thing.

[00:05:13] Dana Whitfield: Sure. It's a few things. The product sort of stalled, they haven't shipped anything meaningful in a long time. Support got slow. And it doesn't really play well with how we've set up our environments now. It was fine when we were smaller, it's not fine now.

[00:06:06] Alex Chen: Yeah, that tracks. We hear the "it was fine when we were smaller" thing a lot, honestly.

[00:06:22] Dana Whitfield: [laughs] I'm sure.

[00:06:29] Alex Chen: And the scripts — are those things you'd want to retire too, or do some of them stay?

[00:06:45] Dana Whitfield: Ideally most of them get retired. There's maybe a handful that are very specific to us that'll stick around, but the goal is one place people go instead of, you know, a wiki page that says "run this, then run that, then ping Kev if it breaks."

[00:07:34] Alex Chen: [laughs] Every company has a Kev.

[00:07:40] Dana Whitfield: Every company has a Kev. Our Kev is very tired.

[00:07:53] Alex Chen: Okay, so, um — who's actually going to be using this day to day? Like, is it just your team, or is it broader?

[00:08:20] Dana Whitfield: Broader. So my team administers it, but the users are engineering generally. We did a count when we were putting the business case together, and it's about 120 engineers who'd need access.

[00:08:59] Alex Chen: About 120. Okay. And is that — sorry, is that everyone who'd log in, or is that the ones who'd log in regularly?

[00:09:18] Dana Whitfield: That's everyone who'd need an account. We went through it team by team. Some of them will use it every day, some of them once a week, but they all need access.

[00:09:45] Alex Chen: Got it. That's helpful. A lot of people give me a number that's, like, a vibe, so it's nice to hear you actually counted.

[00:10:04] Dana Whitfield: We counted. Twice, actually, because finance asked.

[00:10:17] Alex Chen: [laughs] Of course they did. Um, and — so finance is already involved, which I guess leads me to the budget question. Where are you on that? Is this something you're still trying to get funded, or —

[00:10:53] Dana Whitfield: No, it's funded. Budget's approved for this fiscal year. That was the whole point of doing the count twice. So we're not in the "go convince someone" phase, we're in the "pick the right thing and do it" phase.

[00:11:36] Alex Chen: That's great. That makes my life a lot easier, honestly. Who signed off on it, just so I understand who else I'll meet?

[00:11:55] Dana Whitfield: My boss, Marcus. He's VP of Engineering. He's supportive, he's the one who'll sign, but he's pretty hands-off until it's time to look at actual numbers. I'll probably pull him into the next one.

[00:12:34] Alex Chen: Perfect. I'd love that.

[00:12:41] Dana Whitfield: Yeah.

[00:12:47] Alex Chen: So — okay. Let me ask about the, um, the workflow side for a second. When somebody on one of those teams needs, say, a new environment today, walk me through what happens.

[00:13:20] Dana Whitfield: Oh god. Okay. So they file a ticket, or they don't file a ticket and they just DM someone on my team, which is worse —

[00:13:43] Alex Chen: [laughs]

[00:13:46] Dana Whitfield: — and then someone runs one of the scripts, and if the script works, great, and if it doesn't, they go into the legacy tool and click around, and then it's a half day before the person actually has what they asked for. On a good day.

[00:14:29] Alex Chen: And on a bad day?

[00:14:35] Dana Whitfield: On a bad day it's Kev.

[00:14:42] Alex Chen: [laughs] Right. Okay, so self-service is a big part of this.

[00:14:55] Dana Whitfield: Self-service is most of it. If people could just get what they need without talking to us, that's the win. My team would get probably a day a week back.

[00:15:24] Alex Chen: Yeah. And that's something we do pretty well, I'll show you in a sec. Before I do, um, you mentioned in your email you'd looked at our tiers already?

[00:15:50] Dana Whitfield: Yes. So we looked at the pricing page. The entry tier is not going to work for us, we need the stuff that's in Pro. The approval workflows, the audit history, and the, um, the environment templates. We'd outgrow the entry tier basically immediately.

[00:16:46] Alex Chen: Yeah, I'd agree with that. Honestly, for a group your size, I wouldn't even pitch you the entry tier. It's built for, like, a single team kicking the tires.

[00:17:15] Dana Whitfield: Right. So Pro is what we're planning around.

[00:17:25] Alex Chen: Okay. And you don't need the, uh, the stuff that's only in Enterprise? Like dedicated tenancy, the custom data residency, that sort of thing?

[00:17:51] Dana Whitfield: No. We talked about it. We don't need it. Pro covers it.

[00:18:04] Alex Chen: Cool. That's easy then.

[00:18:11] Dana Whitfield: Easy is good.

[00:18:17] Alex Chen: Let me share my screen real quick. Can you see — do you see a browser window?

[00:18:34] Dana Whitfield: I see your, um, I see your inbox, actually.

[00:18:43] Alex Chen: Oh no. Okay. Hang on. [pause] How about now?

[00:19:00] Dana Whitfield: Now I see the product.

[00:19:06] Alex Chen: Great, sorry about that. Nothing exciting in there, I promise. So this is the self-service catalog. The idea is your team defines templates, and an engineer comes in here and just picks one. So, like, "I need a preview environment for this branch," click, and it provisions with whatever guardrails you set.

[00:20:08] Dana Whitfield: And the guardrails — are those per team or global?

[00:20:21] Alex Chen: Both. You can set a global default and then override per team. So if, say, one group needs a bigger instance size, you give them that without giving it to everyone.

[00:20:54] Dana Whitfield: Okay, that's good. That's actually one of the things the legacy tool can't do, it's all-or-nothing.

[00:21:14] Alex Chen: Yeah. And then the approvals piece — this is Pro — if someone asks for something outside the guardrails, it routes to whoever you designate. They get a Slack notification, approve or reject, done.

[00:21:53] Dana Whitfield: Does it log who approved it?

[00:21:59] Alex Chen: Yep, that's the audit history. Everything's logged, exportable.

[00:22:12] Dana Whitfield: Okay. Our security folks will like that.

[00:22:22] Alex Chen: They usually do. Um, can I ask about the scripts again? When you migrate off, do you have a sense of how many of those you'd want to recreate as templates?

[00:22:51] Dana Whitfield: Rough guess, a dozen or so real ones. There's a long tail of stuff nobody uses.

[00:23:11] Alex Chen: Okay. That's manageable. Some teams bring us, like, hundreds. [inaudible] a dozen is very doable.

[00:23:31] Dana Whitfield: Sorry, you cut out for a second there.

[00:23:37] Alex Chen: Oh, sorry — I said a dozen is very doable. Some teams bring way more.

[00:23:50] Dana Whitfield: Got it. Yeah. We'd probably want help with the migration though. My team is stretched.

[00:24:10] Alex Chen: Yeah, we have an implementation package for exactly that. We can go into it more next time, it's scoped per customer, but basically our team does the heavy lifting on templates and the cut-over.

[00:24:46] Dana Whitfield: That'd be good. Let's definitely talk about that.

[00:24:56] Alex Chen: Will do. I'll write it down. Um — okay, so, timeline-wise. You said the legacy vendor decision is made. Is there a hard date you need to be off them by, or is it more "as soon as we're ready"?

[00:25:35] Dana Whitfield: There's a date, I just don't have it in front of me, and I want to check with Marcus before I tell you something wrong. Can we cover that next time?

[00:26:01] Alex Chen: Of course. No problem.

[00:26:07] Dana Whitfield: I know roughly, I just don't want to commit to it.

[00:26:17] Alex Chen: Totally fair. Um, let me stop sharing. [pause] Okay. A couple more questions and then I'll let you go. How are you thinking about term? Like one year, multi-year?

[00:26:53] Dana Whitfield: Probably multi-year, but again, Marcus. He has opinions on that. I'd rather he's in the room.

[00:27:13] Alex Chen: Makes sense. I'll hold all the commercial stuff for when he's on.

[00:27:26] Dana Whitfield: Yeah, that's the right call.

[00:27:32] Alex Chen: And then, um, SSO — you're on Okta?

[00:27:45] Dana Whitfield: We are.

[00:27:49] Alex Chen: Okay, that's standard, no issue there, it's included in Pro.

[00:28:02] Dana Whitfield: Great.

[00:28:05] Alex Chen: And who else would you want in the technical conversation? Anyone from security, or is it you?

[00:28:25] Dana Whitfield: Me, mostly. Maybe one of my leads. Security will want your SOC 2 report and they'll ask the usual questions, but I can route that async. It shouldn't need a meeting.

[00:28:57] Alex Chen: Perfect, I'll send the SOC 2 over with the follow-up. Actually — do you want it now, or with the recap?

[00:29:17] Dana Whitfield: With the recap is fine.

[00:29:23] Alex Chen: Okay.

[00:29:27] Dana Whitfield: Um, sorry, I'm looking at the clock. I should jump in about two minutes.

[00:29:40] Alex Chen: No, yeah, let's wrap. So what I heard — you're leaving the legacy vendor, retiring most of the scripts, about 120 engineers need access, budget's approved, and you're planning around Pro, not entry. Marcus signs. And next time we go deeper on the technical stuff and do commercials with him on.

[00:30:42] Dana Whitfield: That's exactly right. Yeah.

[00:30:48] Alex Chen: Great. Can I send you a couple of times for the next one?

[00:30:58] Dana Whitfield: Yes, please. Two weeks out is probably realistic, Marcus's calendar is a disaster.

[00:31:14] Alex Chen: Ha. Okay, I'll look at the week of the 24th or so and send options.

[00:31:27] Dana Whitfield: Perfect. And, um, if you can send something short on the implementation package beforehand, I'll forward it to Marcus so he's not seeing it cold.

[00:31:54] Alex Chen: Will do. One-pager, I'll keep it short.

[00:32:03] Dana Whitfield: Short is good. He doesn't read long things.

[00:32:13] Alex Chen: [laughs] Noted.

[00:32:20] Dana Whitfield: Okay, I really do have to run. Thanks Alex, this was helpful.

[00:32:33] Alex Chen: Thank you, Dana. Talk soon.

[00:32:39] Dana Whitfield: Bye!

[00:32:43] Alex Chen: Bye.

[00:32:46] [Dana Whitfield left the call]

[00:33:25] Alex Chen: [to self] Okay, SOC 2, one-pager, times for Marcus. [recording stopped]
