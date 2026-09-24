# Call transcript

**Call ID:** C2
**Date:** 2026-08-26
**Type:** Technical deep-dive and commercials
**Duration:** 47 min
**Account:** Retool (retool.com)
**Participants:**
- Alex Chen, Account Executive
- Dana Whitfield, Director of Platform Engineering, Retool
- Marcus Oyelaran, VP Engineering, Retool (joined late)

> Synthetic transcript for a product demo. All people are fictional; this is not a real conversation with Retool.

---

[00:00:15] Alex Chen: Hey Dana.

[00:00:25] Dana Whitfield: Hey! Marcus is going to be a few minutes late, he's stuck in another thing. He said start without him.

[00:00:55] Alex Chen: Sure, no problem. Do you want to do the technical stuff first then, and save commercials for when he's here?

[00:01:26] Dana Whitfield: Yeah, that's what I was going to suggest.

[00:01:36] Alex Chen: Great. So I sent over the SOC 2 and the one-pager — did security have any questions?

[00:02:06] Dana Whitfield: A couple, mostly about data retention on the audit logs. I'll forward them. Nothing scary.

[00:02:36] Alex Chen: Okay, cool. So the stuff you'd flagged last time for the deep-dive was — templates, the approval routing, and how the Okta integration handles groups. Is that still the list?

[00:03:32] Dana Whitfield: That's the list. Plus I want to understand the API a bit, because a couple of the scripts we're keeping would need to call you.

[00:04:07] Alex Chen: Yep. Let's start with groups, that's the quickest. So with Okta, you map your Okta groups to roles in our side. When someone's added to a group in Okta, they get the role automatically. SCIM handles deprovisioning.

[00:05:18] Dana Whitfield: And that's in Pro, right? Not an Enterprise-only thing?

[00:05:33] Alex Chen: SCIM's in Pro, yes.

[00:05:43] Dana Whitfield: Okay, good.

[00:05:53] Alex Chen: On templates, um, let me share. [pause] Can you see it?

[00:06:18] Dana Whitfield: Yep.

[00:06:23] Alex Chen: So templates are just YAML under the hood. You can author them in the UI or check them into a repo and we sync. Most platform teams go the repo route.

[00:07:14] Dana Whitfield: Repo route, definitely. Do you support, um, parameters with validation? Like, "instance size must be one of these three"?

[00:07:54] Alex Chen: Yes. Enums, ranges, regex. And the validation happens before anything provisions, so people get an error in the form, not a failed job.

[00:08:39] Dana Whitfield: Oh, that's nice. That's a real problem we have now. People find out twenty minutes in that they typo'd something.

[00:09:15] Alex Chen: Yeah. Um — and on the API, it's REST, everything the UI does is in the API. Rate limits are generous on Pro, I can send the doc.

[00:10:00] Dana Whitfield: Please.

[00:10:05] [Marcus Oyelaran joined the call]

[00:10:16] Marcus Oyelaran: Hey, sorry, sorry. Hi everyone.

[00:10:32] Alex Chen: Hey Marcus! Alex, nice to meet you.

[00:10:43] Marcus Oyelaran: Nice to meet you. Sorry, the thing before this ran way over. Dana, can you give me the thirty-second version of where we are? I read the one-pager but that's it.

[00:11:32] Dana Whitfield: Sure. So — we're going with Pro, we talked about that last time, entry tier doesn't have the approvals or audit stuff. We're mid-way through the technical questions, Okta and SCIM are fine, templates look good, we were just on the API. Security has a couple of small questions on retention. And we haven't done commercials, we were waiting for you.

[00:13:26] Marcus Oyelaran: Okay. And the seat count's still what we took to finance?

[00:13:42] Dana Whitfield: Yeah, 120. Same number I gave Alex on the first call. Nothing's changed there.

[00:14:09] Marcus Oyelaran: Good. Okay. Carry on, don't let me derail you.

[00:14:25] Alex Chen: No, that's great, thanks Dana. Um, so we were on the API. Marcus, the short version is anything you can do in the UI, you can do in the API, so the handful of scripts Dana's keeping can call in.

[00:15:30] Marcus Oyelaran: Makes sense.

[00:15:36] Dana Whitfield: Can I ask one more on templates, sorry — versioning. If I change a template, what happens to environments already created from the old version?

[00:16:19] Alex Chen: They stay on the old version until someone chooses to update. You can see which environments are on which version, and you can force an upgrade if you need to.

[00:17:08] Dana Whitfield: Okay. Good. That's the right behaviour.

[00:17:24] Alex Chen: Anything else technical, or should we move on?

[00:17:41] Dana Whitfield: I think I'm good. I'll send the security questions over email.

[00:17:57] Alex Chen: Perfect. So, um, let's talk about getting you live, and then the commercial stuff. Onboarding timeline — Dana, last time you said there was a date you had to be off the legacy vendor by?

[00:18:56] Dana Whitfield: Yeah. So our contract with them runs out at the end of October. We don't want to renew, even for a month, if we can avoid it.

[00:19:40] Marcus Oyelaran: We're not renewing. I'm not paying them for another month.

[00:19:56] Dana Whitfield: [laughs] Okay, we're not renewing.

[00:20:07] Alex Chen: So realistically — um, how long does it take you guys to get through legal and procurement once we have paper?

[00:20:45] Dana Whitfield: Couple of weeks. It's not heavy for something this size.

[00:21:07] Alex Chen: Okay. And our implementation package — typical time from signature to cut-over is four to six weeks for a dozen templates.

[00:21:50] Marcus Oyelaran: That's tight.

[00:21:55] Dana Whitfield: It's tight, but — wait, if we sign early September, six weeks is mid-October. That works?

[00:22:33] Alex Chen: That works if we sign early September. If it slips, it gets tight.

[00:22:55] Marcus Oyelaran: So what are we saying for go-live? I want an actual date, not "sometime in the fall."

[00:23:22] Dana Whitfield: I'd rather have a buffer. What about — could we run both in parallel for the last couple of weeks of October, and then officially go live on the first?

[00:24:11] Alex Chen: The first of November?

[00:24:22] Dana Whitfield: Yeah. November 1. Parallel run before that, legacy switched off at the end of October, and November 1 is the day we're officially on you.

[00:25:05] Marcus Oyelaran: I like that. Clean.

[00:25:16] Alex Chen: That works for us. So November 1 is the go-live and subscription start, and we'd have the implementation work happening in the weeks before.

[00:25:59] Dana Whitfield: Right. Wait, does the subscription need to start earlier for the parallel run? Like, do we need to be paying to be using it?

[00:26:37] Alex Chen: No — implementation happens in a sandbox tenant, that's covered by the services package. Subscription starts November 1.

[00:27:15] Dana Whitfield: Okay, great.

[00:27:21] Marcus Oyelaran: Good.

[00:27:26] Alex Chen: Speaking of which — the implementation package. Do you want that in? From what Dana said last time, it sounded like yes.

[00:27:59] Dana Whitfield: Yes. Definitely. My team does not have the capacity to do the migration ourselves on that timeline.

[00:28:31] Marcus Oyelaran: Yeah, put it in. I'd rather pay for it than have Dana's team burn out doing it.

[00:28:58] Alex Chen: Okay, implementation services, in. So — term. Marcus, Dana said you'd have opinions.

[00:29:31] Marcus Oyelaran: [laughs] I do. Two years. I don't want to re-paper this every twelve months, it's a waste of everyone's time and procurement hates it.

[00:30:14] Alex Chen: Two-year term, okay. Annual billing within that, or upfront?

[00:30:36] Marcus Oyelaran: Annual is fine.

[00:30:47] Alex Chen: And payment terms — our standard is net 30.

[00:31:03] Marcus Oyelaran: Net 30 is fine. That's what we do with everyone.

[00:31:19] Alex Chen: Great, easy. And then, um — price. Do you want me to walk you through list first, or do you already have a number in your head?

[00:31:57] Marcus Oyelaran: I've seen list on your site. Look, I'll just be direct. We're committing to two years, we're paying for implementation, we're a pretty straightforward customer. I'd like to see something around 12 percent off list.

[00:33:08] Alex Chen: Around 12 percent.

[00:33:13] Marcus Oyelaran: Yeah. Around there.

[00:33:24] Alex Chen: Honestly, that's workable. With a two-year commitment and Pro, 12 percent is within what I can do. I don't think I'd need to go back and forth internally on that.

[00:34:13] Marcus Oyelaran: Great. Then I don't need to haggle.

[00:34:24] Dana Whitfield: [laughs] He was ready to haggle.

[00:34:35] Marcus Oyelaran: I was ready to haggle. I'm a little disappointed.

[00:34:51] Alex Chen: [laughs] I can make it harder if you want.

[00:35:02] Marcus Oyelaran: No, no. Please don't.

[00:35:13] Alex Chen: Okay, so just to make sure I have everything for the quote. Pro tier, 120 seats, implementation services, two-year term, annual billing, net 30, around 12 percent off list, go-live November 1.

[00:36:28] Dana Whitfield: Yep.

[00:36:34] Marcus Oyelaran: That's it.

[00:36:39] Alex Chen: And Marcus, you're the signer?

[00:36:50] Marcus Oyelaran: I'm the signer. Send it to me, cc Dana.

[00:37:06] Alex Chen: Perfect.

[00:37:12] Dana Whitfield: Oh, one thing on onboarding — sorry, going back. The parallel run. Do we need to tell you which teams go first, or do you have a playbook?

[00:37:55] Alex Chen: We have a playbook, but we'll want your input. Usually you start with one friendly team, the ones who complain the most about the current process —

[00:38:33] Dana Whitfield: That's everyone.

[00:38:39] Alex Chen: [laughs] — then roll out wider once the templates are solid. The implementation lead will set up a kickoff and go through that with you.

[00:39:17] Dana Whitfield: Okay. I'd want the infra team first, they're the most, um, opinionated.

[00:39:44] Marcus Oyelaran: That's a nice way of putting it.

[00:39:55] Dana Whitfield: [laughs]

[00:40:00] Alex Chen: Opinionated is good for a pilot. They'll find everything.

[00:40:16] Marcus Oyelaran: They will find everything.

[00:40:27] Alex Chen: Um, and then on the kickoff — who from your side would be on that? Dana, you plus a couple of leads?

[00:41:00] Dana Whitfield: Me, two of my leads, and probably our Kev.

[00:41:16] Alex Chen: [laughs] Kev has to be there.

[00:41:27] Marcus Oyelaran: Who's Kev?

[00:41:32] Dana Whitfield: I'll explain later.

[00:41:43] Marcus Oyelaran: Okay. [laughs]

[00:41:54] Alex Chen: So, next steps. I'll send the quote and the order form by end of week. You'll send the security questions. Once security's happy and you've got the paper, legal review, and we're aiming to sign in early September so implementation can start right after.

[00:43:10] Marcus Oyelaran: Sounds right. Can you put the go-live date and the parallel run in the order form, or at least in a cover note? I want it written down somewhere.

[00:43:48] Alex Chen: I'll put the November 1 start in the order form and the parallel run plan in the implementation SOW.

[00:44:20] Marcus Oyelaran: Good.

[00:44:26] Dana Whitfield: And the SOW is separate from the order form?

[00:44:42] Alex Chen: It's attached to it. Same signature.

[00:44:53] Dana Whitfield: Okay, great. One signature, I like that.

[00:45:09] Marcus Oyelaran: Anything else from you, Dana?

[00:45:20] Dana Whitfield: No, I think that's everything. This was painless.

[00:45:36] Alex Chen: That's the goal. Um, Marcus, anything from you?

[00:45:52] Marcus Oyelaran: Nope. Thanks, Alex. Good to meet you.

[00:46:03] Alex Chen: You too. Thanks both.

[00:46:14] Dana Whitfield: Thanks, bye!

[00:46:20] [Marcus Oyelaran left the call]

[00:46:25] [Dana Whitfield left the call]
