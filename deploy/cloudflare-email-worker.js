/**
 * Cloudflare Email Worker: receives mail for your inbound domain and
 * posts it to GAJ. Cloudflare Email Routing is free.
 *
 * Setup (done in Phase 5, once GAJ is online):
 *   1. Cloudflare dashboard -> your domain -> Email -> Email Routing -> enable.
 *   2. Workers & Pages -> Create Worker -> paste this file -> Deploy.
 *   3. Worker -> Settings -> Variables:
 *        JOBTRACK_URL    = https://your-jobtrack-site/inbound/email
 *        INBOUND_SECRET  = the same value as INBOUND_WEBHOOK_SECRET in .env  (type: Secret)
 *   4. Email Routing -> Routing rules -> Catch-all address -> Action "Send to a Worker"
 *      -> choose this Worker.
 */
export default {
  async email(message, env) {
    const raw = await new Response(message.raw).arrayBuffer();

    const response = await fetch(env.JOBTRACK_URL, {
      method: "POST",
      headers: {
        "Content-Type": "message/rfc822",
        "X-JobTrack-Secret": env.INBOUND_SECRET,
        "X-Envelope-To": message.to,
      },
      body: raw,
    });

    // A temporary failure (GAJ restarting) makes the sender retry later
    if (response.status >= 500) {
      message.setReject("GAJ is temporarily unavailable, try again later");
    }
  },
};
