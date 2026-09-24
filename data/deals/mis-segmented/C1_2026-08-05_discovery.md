# Call transcript

**Call ID:** C1
**Date:** 2026-08-05
**Type:** Discovery
**Duration:** 38 min
**Account:** MongoDB (mongodb.com)
**Participants:**
- Jordan Mwangi, Account Executive
- Sam Devarakonda, Engineering Manager, Platform, MongoDB

> Synthetic transcript for a product demo. All people are fictional; this is not a real conversation with MongoDB.

---

[00:00:13] Jordan Mwangi: Hey Sam, how's it going?

[00:00:22] Sam Devarakonda: Hey! Good, good. Sorry, I'm in a phone booth, it's a little echoey.

[00:00:40] Jordan Mwangi: No, you sound fine. Is that one of those little office pods?

[00:00:58] Sam Devarakonda: Yeah, it's a pod. There's a fan in here that sounds like a jet engine, so if you hear that, that's what it is.

[00:01:25] Jordan Mwangi: [laughs] Got it. Thanks for making time. I saw you signed up for the trial last week — how's it been?

[00:01:52] Sam Devarakonda: Honestly? Pretty good. I only got through the getting-started stuff, but a couple of people on my team poked at it and they were into it.

[00:02:27] Jordan Mwangi: Oh, nice. That's a good sign. Um, so, I'd love to just understand where you're at. Who you are, what your team does, what made you sign up.

[00:03:07] Sam Devarakonda: Yeah, sure. So I manage the platform group. We're, um — it's our little team, basically. We own the internal platform: CI, environments, the deploy tooling, the golden paths, all of that.

[00:04:05] Jordan Mwangi: Okay. How big is the team?

[00:04:19] Sam Devarakonda: So the platform group is about 40 people. That's, like, engineers plus a couple of TPMs. We're split into a few squads but it all rolls up to me.

[00:05:03] Jordan Mwangi: About 40. Okay. And when you say you own the platform, is that for — like, who are your customers? Other engineering teams?

[00:05:35] Sam Devarakonda: Um, kind of, but honestly, we operate pretty independently. We have our own roadmap, we pick our own tools. We don't really have to, like, run things by a central architecture board or anything. Which is nice. It's kind of why I like the job.

[00:06:42] Jordan Mwangi: That's great. That's rare.

[00:06:51] Sam Devarakonda: It is. I've been at places where you need six approvals to install a linter.

[00:07:13] Jordan Mwangi: [laughs] Oh, I know. I've sold into those places. It's — yeah. It takes a while.

[00:07:35] Sam Devarakonda: [laughs] I bet.

[00:07:44] Jordan Mwangi: So, um, what's the problem you're trying to solve? What made you go looking?

[00:08:06] Sam Devarakonda: So, the main thing is environment sprawl. We have a ton of preview environments that people spin up and never tear down, and nobody really knows who owns what. It's costing us money and it's kind of a mess.

[00:09:05] Jordan Mwangi: Yeah. How are they getting spun up today?

[00:09:18] Sam Devarakonda: Terraform, mostly, plus some, uh, some homegrown stuff. There's a Slack bot one of my engineers wrote that kind of does it. It's actually pretty good, but it has no concept of expiry, and it doesn't know about cost.

[00:10:16] Jordan Mwangi: Got it. So TTLs and ownership are the big gaps.

[00:10:34] Sam Devarakonda: TTLs, ownership, and cost visibility. If I could see, like, "this team is spending this much on preview environments," that would be a huge win. My director asks me that every month and I kind of make it up.

[00:11:32] Jordan Mwangi: [laughs] We can fix that. That's actually one of our strongest areas. Um, let me — do you want to see it? Or do you want to keep talking first?

[00:12:08] Sam Devarakonda: Let's talk a little more and then show me.

[00:12:21] Jordan Mwangi: Sure. So who would actually be using it? Your 40, or broader?

[00:12:43] Sam Devarakonda: So that's the thing. It'd be my team, and then the SRE group that sits next to us. They're not in my org, but we work super closely and they'd be the other heavy users. So I was thinking 60 seats. That covers my folks and leaves room for the SRE people.

[00:13:55] Jordan Mwangi: 60 seats. Okay. And the SRE group — do they have their own tooling budget, or would this come out of yours?

[00:14:26] Sam Devarakonda: It'd come out of mine. We have our own budget line for tooling. I just figured it's easier to buy it once and give them access than to have two contracts.

[00:15:06] Jordan Mwangi: Totally, that makes sense. Um — so you have your own budget line. Does that mean you can sign for this yourself?

[00:15:37] Sam Devarakonda: Uh. Sort of? So, I can approve stuff up to a point. But procurement has to sign off on anything over a certain threshold, and honestly I'm not sure what the threshold is. I've never bought anything big enough to find out.

[00:16:40] Jordan Mwangi: [laughs] Okay.

[00:16:44] Sam Devarakonda: Like, I've bought a few SaaS tools on my card, and those were fine. This would be bigger than those. So I'd guess procurement gets involved, but I genuinely don't know.

[00:17:29] Jordan Mwangi: No, that's fine. Could you find out? Just so we don't get surprised later.

[00:17:47] Sam Devarakonda: Yeah, I'll ask. I think there's someone in procurement I can ping.

[00:18:05] Jordan Mwangi: Perfect. Um — okay, and in terms of, like, your environment. Cloud-wise, you're on AWS?

[00:18:36] Sam Devarakonda: AWS mostly, a little GCP. We're pretty much all Kubernetes.

[00:18:54] Jordan Mwangi: Okay, great, that's our sweet spot. Let me share my screen. [pause] Can you see it?

[00:19:20] Sam Devarakonda: Yep, I see it. Sorry, the fan just came on.

[00:19:34] Jordan Mwangi: [laughs] I can hear it. It's fine. So, this is the environments view. Every environment, who created it, which team, when it expires, and what it's costing.

[00:20:18] Sam Devarakonda: Oh — wait, cost per environment? How are you getting that?

[00:20:36] Jordan Mwangi: We read the tags off your cloud resources and pull from the billing API. It's not to the penny, it's like a day behind, but it's close.

[00:21:12] Sam Devarakonda: That's — yeah, that's exactly what my director wants.

[00:21:25] Jordan Mwangi: And then here, TTLs. You set a default, like "preview environments expire after 72 hours," and people can extend, but they have to click. And the owner gets a Slack ping before it dies.

[00:22:19] Sam Devarakonda: Can they extend forever? Because people will just click extend forever.

[00:22:37] Jordan Mwangi: [laughs] You can cap it. Like, "max three extensions, then it needs approval."

[00:22:59] Sam Devarakonda: Oh, nice. Okay.

[00:23:08] Jordan Mwangi: And the approval can route to you, or a team lead, or whoever.

[00:23:26] Sam Devarakonda: Can I just — is this, like, the paid tier? Or is this in the trial?

[00:23:44] Jordan Mwangi: This is Pro. The trial's on Pro, so you've got all of it.

[00:24:02] Sam Devarakonda: Okay, cool. Because I think we'd want Pro. The entry tier didn't have the approval stuff, from what I saw.

[00:24:28] Jordan Mwangi: Right, the approval routing and cost views are Pro. Honestly, for a team your size, Pro's the right fit.

[00:25:00] Sam Devarakonda: Yeah. I mean, we're not huge. We don't need, like, a big enterprise thing.

[00:25:17] Jordan Mwangi: Totally. Um, let me show you one more thing — the Slack integration. You said one of your engineers built a bot?

[00:25:49] Sam Devarakonda: Yeah, Deepa. She'll be sad if we replace it.

[00:26:02] Jordan Mwangi: [laughs] Well, she can extend ours. We have an API, and the Slack app's open, so if she wants to keep her commands she can wire them to our API.

[00:26:42] Sam Devarakonda: Oh, she'd like that. She'd like that a lot. She's very attached to her bot.

[00:27:00] Jordan Mwangi: [laughs] Everyone's attached to their bot.

[00:27:14] Sam Devarakonda: [inaudible] — sorry, what was that last part?

[00:27:22] Jordan Mwangi: Oh, I said everyone's attached to their bot.

[00:27:36] Sam Devarakonda: [laughs] True. Okay. Um, this looks good. Really good, actually.

[00:27:54] Jordan Mwangi: Great. Let me stop sharing. [pause] So — a couple more questions. SSO. What are you on?

[00:28:25] Sam Devarakonda: Okta. I think. Actually — yeah, Okta. There's an IT team that manages it, I'd have to ask them to set up the app.

[00:28:56] Jordan Mwangi: Okay, that's standard, we have an Okta app in their catalog. Should be quick.

[00:29:19] Sam Devarakonda: Good.

[00:29:23] Jordan Mwangi: And, um, timing. When would you want to get going?

[00:29:41] Sam Devarakonda: Hm. Not right away. We have a big migration landing over the next couple of months, and I don't want to throw a new tool at the team in the middle of it. So probably after that. I'll figure out a date.

[00:30:34] Jordan Mwangi: Okay. We can talk about exact timing next time.

[00:30:48] Sam Devarakonda: Yeah.

[00:30:52] Jordan Mwangi: And, uh, anyone else I should be talking to? Or is it pretty much you?

[00:31:15] Sam Devarakonda: Pretty much me. Like I said, we operate pretty independently. Maybe my director at some point, but he trusts me on tools.

[00:31:50] Jordan Mwangi: Great. And the SRE lead? Should we loop them in?

[00:32:08] Sam Devarakonda: Um, I can. She's pretty easygoing. She'll use whatever we pick as long as it has an API.

[00:32:35] Jordan Mwangi: [laughs] That's the right requirement.

[00:32:44] Sam Devarakonda: [laughs] Yeah.

[00:32:53] Jordan Mwangi: Okay. Um — I think for next time, it'd be good to talk commercials. Is there anything you want me to send you before that?

[00:33:24] Sam Devarakonda: Uh, pricing for Pro with 60 seats would be good, so I can start thinking about it. And whatever you have on security, in case procurement asks.

[00:34:00] Jordan Mwangi: Will do. SOC 2, the security whitepaper, and a rough quote.

[00:34:18] Sam Devarakonda: Perfect.

[00:34:22] Jordan Mwangi: And you'll find out about the procurement threshold?

[00:34:35] Sam Devarakonda: I'll find out. I'll ask around.

[00:34:44] Jordan Mwangi: Cool. Um, and — sorry, one last thing. The migration you mentioned. Is that something we could help with, or totally unrelated?

[00:35:20] Sam Devarakonda: Totally unrelated. It's a, um, a database version upgrade across a bunch of services. It's just a lot of work.

[00:35:51] Jordan Mwangi: [laughs] Of course it is. Okay. Good luck with that.

[00:36:05] Sam Devarakonda: Thanks. We'll need it. It's our little team against, like, a hundred services.

[00:36:27] Jordan Mwangi: [laughs] That sounds rough.

[00:36:36] Sam Devarakonda: It's fine. We like a challenge. Okay — I've got to get out of this pod, someone's waiting outside looking at me.

[00:37:03] Jordan Mwangi: [laughs] Go, go. Thanks Sam, great chatting.

[00:37:16] Sam Devarakonda: You too! Talk soon.

[00:37:25] [Sam Devarakonda left the call]
