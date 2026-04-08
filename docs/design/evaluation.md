# Reddit Network Discovery App -- Product Evaluation

## 1. The Problem (Not the Solution)

> "Fall in love with the problem, not the solution." -- Marty Cagan, *Inspired*

**The core problem:** Reddit's native tools optimize for *content consumption* (sorting posts by hot/top/new), but they are terrible at **people discovery** and **community discovery**. There's no way to answer:

- "Who are the most insightful voices in this thread?"
- "What other communities do smart people in r/datascience hang out in?"
- "Show me everything this brilliant commenter has said about topics I care about."

Reddit treats users as anonymous content generators. You consume posts, not people. But **the highest-signal content discovery is people-driven, not algorithm-driven** -- if someone writes one great comment on distributed systems, their other comments and subscriptions are a goldmine of curated knowledge.

**Who has this problem acutely?**

| Persona | Pain | Frequency |
|---------|------|-----------|
| **Researchers / domain learners** | Want to find experts and follow their trails to curate a personalized knowledge graph | Daily |
| **Content creators / community builders** | Want to find where their audience lives and who the thought leaders are | Weekly |
| **Recruiters / talent scouts** | Want to identify domain experts by the quality of their contributions | Weekly |
| **Investors / trend watchers** | Want early signals on emerging communities and who the early movers are | Weekly |

---

## 2. Garry Tan's Office Hours: Six Forcing Questions

Applying YC's `/office-hours` framework from [gstack](https://github.com/garrytan/gstack):

### Q1: "Who is your customer and what is the specific problem?"

**Customer:** Knowledge workers who use Reddit as a learning resource -- data scientists, developers, researchers, analysts. Not casual Reddit browsers.

**Specific problem:** They find a great thread, read one amazing comment, and then... nothing. There's no way to discover who that person is, what else they know, or what adjacent communities they've already curated for themselves.

**Verdict:** The problem is real but niche. The forcing question is: **does this niche pay?**

### Q2: "Interest does not equal demand -- what behavior proves demand?"

This is the critical question. Signals of existing demand:

- **Positive:** Tools like Reddit Investigator, SnoopSnoo, Redective already exist (user profile analyzers). People manually click through user histories. Subreddit recommendation threads are consistently popular. The behavior exists -- it's just painful and manual.
- **Concerning:** Most of these tools are free, abandoned side projects. Nobody has built a sustainable business here. This could mean "not enough demand to pay" or "nobody has executed well enough yet."

**Verdict:** Behavior exists. Willingness to pay is unproven. This needs validation before building.

### Q3: "The status quo is the real competitor"

Your competition is NOT other Reddit tools. It's:

1. **Manually clicking a user's profile** and scanning their history (free, good enough for casual use)
2. **Twitter/X** as an alternative people-following platform (already built for this)
3. **Not doing it at all** -- most people just consume the thread and move on

**Verdict:** The status quo is "good enough" for most users. You need to deliver a **10x improvement** for a specific use case to overcome inertia. "Slightly easier profile browsing" won't cut it.

### Q4: "Narrow beats wide early"

The feature list as described is already wide:
- Top posts in a subreddit (commodity)
- Top commenters with multi-criteria ranking (novel)
- Cross-subreddit discovery via user history (novel, high-value)
- People following with topic filtering (novel, complex)
- LLM-based quality scoring (novel, expensive)

**Verdict:** Pick ONE wedge. The cross-subreddit discovery via user analysis is the most differentiated. Start there.

### Q5: "Watch, don't demo"

Before building, observe:
- Go to r/datascience. Find a great thread. Try to manually discover what other subreddits the top commenters frequent. Time yourself. Feel the pain. How long does it take? Is it 5 minutes or 50 minutes? The answer determines your appetite.

### Q6: "Specificity is the only currency"

Vague: "Discover content on Reddit."
Specific: "Given a post URL, show me the top 10 commenters ranked by technical depth, and for each one, show me the 5 subreddits they're most active in that are related to the original post's topic."

**The specific version is a product. The vague version is a feature request.**

---

## 3. Cagan's Four Risks Assessment (Inspired)

### Value Risk: "Will anyone use this?"

**Medium-High Risk.** The behavior exists (people do profile-stalk on Reddit), but the question is whether the structured version is *valuable enough* to adopt a new tool. The LLM-based scoring is genuinely novel -- no one else can tell you "this commenter sounds technically deep" vs "this commenter sounds sincere." That's the moat.

### Usability Risk: "Can they figure out how to use it?"

**Low Risk.** The mental model is simple: paste a URL, get insights. The guardrail system (filtering irrelevant subreddits) is the main UX challenge -- how do users express "I care about data science but not hiking" without a complex configuration step?

### Feasibility Risk: "Can we build this?"

**Medium Risk.** Key concerns:

| Challenge | Severity | Notes |
|-----------|----------|-------|
| Reddit API rate limits | High | Reddit aggressively limits API access since 2023 pricing changes. Building on their API is building on a landlord's property. |
| User history access | Medium | Some users have private histories. Many have 10+ years of activity -- scraping this is slow. |
| LLM cost per analysis | Medium | Scoring every comment with an LLM is expensive at scale. Need smart batching/caching. |
| Data freshness | Low | Reddit data is relatively static (comments don't change much after 24h). |

### Business Viability Risk: "Does the business work?"

**High Risk.** This is the biggest concern:

- **Reddit API costs** post-2023 are significant for any tool that needs to read lots of user data
- **LLM inference costs** for quality scoring add up fast
- **Willingness to pay** is unproven -- Reddit's user base skews toward "everything should be free"
- **Platform dependency** -- Reddit can (and has) shut down third-party tools overnight

---

## 4. Shape Up Assessment: Appetite & Shaping

> "How much time is this worth?" -- Ryan Singer, *Shape Up*

### Appetite Check

For a **v0.1 spike** to test the core hypothesis ("cross-subreddit discovery via user analysis is valuable"):

- **2-week appetite** is appropriate
- Scope: CLI tool or simple web app. Input: post URL. Output: top commenters + their subreddit map, filtered by relevance.
- No LLM scoring in v0.1. Start with static metrics (karma, comment frequency).
- No following/tracking in v0.1. That's a separate bet.

### Rabbit Holes to Avoid

- Don't build a full Reddit client
- Don't try to do real-time monitoring in v0.1
- Don't build LLM scoring before validating that people even want the subreddit map
- Don't build user accounts, dashboards, or social features early

### No-Gos

- No storing/caching user data long-term without clear privacy policy (legal risk)
- No trying to circumvent Reddit's API limits
- No building features Reddit already does well (sorting, searching within a subreddit)

---

## 5. CEO Instinct Review (gstack /plan-ceo-review)

Applying Garry Tan's 18 CEO cognitive patterns:

### Reversibility x Magnitude: "Is this a one-way or two-way door?"

Building a v0.1 CLI tool is a **two-way door** -- low cost, easily abandoned. Good. Building a full SaaS with user accounts and paid Reddit API access is a **one-way door** -- don't walk through it until the hypothesis is validated.

### Inversion: "What would make this fail?"

1. Reddit shuts down API access or raises prices further
2. Users try it once, say "cool," and never come back (novelty, not utility)
3. The subreddit recommendations are too noisy -- users get a wall of irrelevant subreddits
4. Privacy backlash -- users feel surveilled when you expose their browsing patterns
5. LLM costs make the unit economics impossible

**#1 and #4 are existential. #3 is solvable. #5 is manageable with smart architecture.**

### Leverage Obsession: "Where does small effort yield massive output?"

The **highest leverage feature** is the relevance filter on subreddit discovery. Without it, you get noise. With it, you get signal. This is the difference between "here are 200 subreddits this user visits" (useless) and "here are 5 subreddits this user visits that are related to distributed systems" (gold).

**This filter IS the product.** Everything else is plumbing.

### Focus as Subtraction: "What NOT to do"

- Don't build "top posts in a subreddit" -- Reddit already does this. It dilutes your value proposition.
- Don't build a general Reddit client -- you'll never compete with Reddit itself or Apollo-style apps.
- Don't try to be a social network (following, feeds) in v1. That's a different company.

---

## 6. Continuous Discovery: Opportunity Solution Tree

> "Frame opportunities from the customer's perspective." -- Teresa Torres, *Continuous Discovery Habits*

```
DESIRED OUTCOME: Users discover high-value subreddits and
experts they wouldn't have found on their own

├── Opportunity: "I found a great thread but can't find 
│   more communities like this"
│   ├── Solution: Subreddit discovery via top commenter analysis
│   ├── Solution: "Similar subreddits" based on user overlap
│   └── Solution: Topic-based subreddit clustering
│
├── Opportunity: "I can't tell which commenters are 
│   actually worth following"
│   ├── Solution: Static ranking (karma, frequency, consistency)
│   ├── Solution: LLM-based quality scoring
│   └── Solution: Community-validated rankings (let users vote)
│
├── Opportunity: "I found an expert but their history is 
│   full of noise"
│   ├── Solution: Topic-filtered activity view
│   ├── Solution: "Best of" summary per user per topic
│   └── Solution: Interest graph per user
│
└── Opportunity: "I want to stay updated on what smart
    people are saying"
    ├── Solution: Follow + topic-filtered digest
    ├── Solution: Weekly email summary
    └── Solution: RSS feed per tracked user+topic
```

**Riskiest assumption to test first:** "Users will act on subreddit recommendations derived from commenter analysis." If they don't, nothing else matters.

---

## 7. Honest Assessment & Recommendations

### Is This a Good Product Idea?

**As described: No -- it's too broad and has unproven demand.**

**Refined to a wedge: Maybe -- with specific conditions.**

The core insight -- **people are the best curators, and Reddit doesn't let you leverage that** -- is genuinely interesting. But "interesting insight" != "viable product."

### What Would Make This a Yes

1. **Find a paying persona.** The best candidate is **content creators** (they'll pay $20-50/mo to find where their audience hangs out) or **recruiters** (they'll pay $100+/mo to find domain experts). Knowledge workers are harder -- they expect free tools.

2. **Validate the wedge.** Build a CLI tool in 2 weeks that takes a post URL and outputs a filtered subreddit map. Share it on Hacker News and relevant subreddits. Measure: do people come back the next week?

3. **Solve the relevance filter.** This is the product. "Given these subreddits a user visits, which ones are relevant to topic X?" This is where LLMs actually add value -- not in scoring individual comments, but in understanding whether r/machinelearning is related to a data science query but r/hiking is not.

4. **De-risk the platform dependency.** Consider whether the same approach works on other platforms (HN, Stack Overflow, Discord). If you're building "people-based community discovery," Reddit is one input, not the whole product.

### Suggested Refinement: "Community Graph Explorer"

**Reframe:** Instead of "Reddit content discovery," position as **"find your next community by following the smartest people in your current one."**

- Input: A URL (Reddit post, HN thread, Stack Overflow question)
- Output: A graph of related communities, weighted by how many high-quality contributors overlap
- Differentiator: LLM-powered relevance scoring ensures you see related communities, not random noise

This is platform-agnostic, solves a clearer problem, and has a more obvious path to monetization (community builders, developer advocates, researchers all need this).

### Concrete Next Steps (Ordered by Risk Reduction)

| Step | What | Why | Time |
|------|------|-----|------|
| 1 | Manual validation | Do the subreddit-discovery process manually for 5 threads. Is the output actually useful? | 1 day |
| 2 | Reddit API feasibility spike | Can you actually pull user histories at the rate you need within API limits and costs? | 2 days |
| 3 | CLI prototype | Post URL in, filtered subreddit map out. No LLM, just frequency analysis + keyword matching. | 1 week |
| 4 | Dogfood + share | Use it yourself for 2 weeks. Share with 10 people. Do they come back? | 2 weeks |
| 5 | Add LLM scoring | Only if step 4 shows retention. Use LLM for relevance filtering, not comment ranking. | 1 week |

---

## 8. Sources & Frameworks Applied

| Source | How Applied |
|--------|------------|
| **Inspired** (Cagan) | Four risks assessment, "fall in love with the problem" framing, value risk as primary concern |
| **Shape Up** (Singer) | Appetite setting, rabbit holes, no-gos, fixed-time variable-scope approach |
| **Continuous Discovery Habits** (Torres) | Opportunity solution tree, assumption mapping, "riskiest assumption first" |
| **Garry Tan's gstack /office-hours** | Six forcing questions, "interest != demand", "status quo is the real competitor", "narrow beats wide" |
| **Garry Tan's gstack /plan-ceo-review** | Reversibility x magnitude, inversion reflex, leverage obsession, focus as subtraction |
| **gstack Ethos: "Boil the Lake"** | Don't half-build features; fully validate the wedge before expanding scope |
| **gstack Ethos: "Search Before Building"** | Layer 1-2-3 knowledge: existing tools (Layer 1), current best practices in content discovery (Layer 2), the people-as-curators insight (Layer 3 -- first principles) |
| **Don't Make Me Think** (Krug) | UX must be self-evident: paste URL, get results. No configuration required for first use. |
| **Design of Everyday Things** (Norman) | Conceptual model: users think in "show me what smart people read," not "analyze commenter subreddit distribution" |
| **Working Backwards** (Bryar & Carr) | Start from the customer experience (the output) and work backward to what needs to be built |
