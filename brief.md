# mera.health Engineering Intern Take-Home

**A hospital sent us this**

## Context

mera.health works directly with hospitals to digitise and organise their patient records. A lot of that work starts the same way: someone at a hospital sends a short email and a data export, and we have to work out what they need.

This is one of those. The hospital and patients are fictional. The email and the mess are realistic.

## What we're giving you

- `email.txt`: a message from the hospital's operations manager.
- `export/`: what they attached. Four CSV files, about 2,000 rows in all: `patients.csv`, `visits.csv`, `lab_results.csv`, `prescriptions.csv`.

The email, in full:

> Hi team,
>
> Our doctors want to see which diabetic patients are overdue for follow-up so the front desk can call them. Export from our system attached. Can you put something together?
>
> Thanks,
> Meenakshi

## What you'll build

Something that answers her request and that the hospital could use. What form that takes is your call. It has to run on our laptop with one or two commands. No login, no deployment.

## What we want to see

The email leaves almost everything undefined, and the export isn't clean. Working out what the request means, and what the data can and can't support, is the task. Building the thing is the easy part.

Alongside the code, we want:

1. **`PLAN.md`**, committed before you or your agent write any code. How you're breaking this down, what you need to find out first, what you're unsure about. Half a page. It's fine if the plan turns out wrong. Don't go back and edit it.
2. **`DECISIONS.md`**, two pages at most:
   - Each term in the email you had to define, the definition you chose, and why.
   - Each problem you found in the data, and what you did about it.
   - Where you chose to flag something for a person to check rather than decide yourself.
   - What your result can't be trusted for.
3. **`reply.txt`**: the email you'd send back to Meenakshi with your result. 200 words at most. She isn't technical and she isn't a doctor.

## You can ask us questions

You may send us one email with up to five questions, as if you were writing to the hospital. We'll reply within one working day. You don't have to wait for the reply to keep working.

What you ask is part of what we look at. So is what you decide not to ask and work out yourself.

## How we expect you to work

We expect you to use an AI coding agent: Claude Code, Cursor, whatever you like. We use them every day. Writing the code is the cheap part now, so the code isn't what we're assessing. We're assessing how you approached the problem: how you broke it down, what you asked the agent to do, where you disagreed with it, and what you checked yourself.

One warning. If you paste the email into an agent and ask it to build something, it will. It will pick a meaning for "diabetic" and a meaning for "overdue" without telling you, and it will produce a confident list. Noticing that is your job.

So please:

- **Send your agent transcripts.** Export your sessions and include them unedited. This is strongly encouraged, not required. If we move to the next step, explaining your approach is part of the evaluation, and the transcript is the best record you'll have of what you did and why. It helps you as much as it helps us.
- **Keep your real git history.** Commit as you go. Don't squash.

A messy transcript where you changed your mind is better than a clean one.

You don't need medical knowledge, and you don't need a paid API. You will need to look a few things up. Tell us what you looked up and where.

## Time

About 4 hours of work. Please don't spend more. If you run out of time, stop and tell us what you'd do next. Send it back within 5 days of receiving it.

## How we'll evaluate you

About half of this is your process and half is what came out of it.

**Process**
1. **Breaking it down.** Did you work out what the question was before answering it?
2. **Working with the agent.** When it guessed, did you notice? What did you check yourself?
3. **Questions.** Did you ask the things that would change what you built?

**Outcome**
4. **Definitions.** Are your meanings for "diabetic" and "overdue" reasoned, and do you know who they wrongly include or leave out?
5. **Care with the data.** This is people's health data. "Roughly right" isn't good enough, and a wrong name on a call list is a real phone call to a real person.
6. **Usefulness.** Could the front desk use what you built on Monday morning? Does your reply tell Meenakshi what she needs to know?

## What to submit

- The code, as a repo link or zip, with its git history and run instructions.
- `PLAN.md`, `DECISIONS.md`, `reply.txt`.
- Your agent transcripts, if you're sharing them.

## What we're not looking for

- A beautiful UI. Plain is fine.
- Finding every problem in the data. Nobody will.
- A long list of technologies.
- Tests, CI, Docker, anything you don't need.

## What will get you rejected

- A list of patients with no explanation of how they got on it.
- Data changed, merged or dropped silently, with no mention in `DECISIONS.md`.
- Work you can't explain. "The AI wrote it" isn't an answer.

## After you submit

If we move forward, a 30 minute call. You'll walk us through your approach, we'll ask about specific moments in it, and then Meenakshi will reply with a follow-up request and we'll see how you'd handle it.
