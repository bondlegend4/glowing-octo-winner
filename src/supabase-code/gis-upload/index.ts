import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
// These will be set as environment variables in your Supabase project
const BEAM_ENDPOINT_URL = Deno.env.get("BEAM_ENDPOINT_URL"); // The URL for your Beam endpoint
const BEAM_AUTH_TOKEN = Deno.env.get("BEAM_AUTH_TOKEN"); // Your Beam API token
serve(async (req)=>{
  // This webhook is triggered by a new file upload
  const payload = await req.json();
  if (payload.type === "INSERT" && payload.table === "objects") {
    const record = payload.record;
    const bucketId = record.bucket_id;
    const filePath = record.name;
    // We only want to trigger for our 'gis-uploads' bucket
    if (bucketId !== 'gis-uploads') {
      return new Response(JSON.stringify({
        message: "Ignoring upload in other bucket."
      }), {
        status: 200
      });
    }
    console.log(`File detected in '${bucketId}': ${filePath}. Triggering Beam processor.`);
    try {
      if (!BEAM_ENDPOINT_URL || !BEAM_AUTH_TOKEN) {
        throw new Error("Beam URL or Auth Token is not set in environment variables.");
      }
      // Call the Beam endpoint to process the file
      const response = await fetch(BEAM_ENDPOINT_URL, {
        method: "POST",
        headers: {
          "Accept": "*/*",
          "Content-Type": "application/json",
          "Authorization": `Bearer ${BEAM_AUTH_TOKEN}`
        },
        body: JSON.stringify({
          bucket: bucketId,
          path: filePath
        })
      });
      if (!response.ok) {
        const errorBody = await response.text();
        throw new Error(`Beam endpoint failed: ${response.status} ${errorBody}`);
      }
      console.log("Successfully triggered Beam processing function.");
      return new Response(JSON.stringify({
        success: true
      }), {
        status: 200
      });
    } catch (error) {
      console.error("Error triggering Beam:", error);
      return new Response(JSON.stringify({
        error: error.message
      }), {
        status: 500
      });
    }
  }
  return new Response(JSON.stringify({
    message: "Payload received, no action taken."
  }), {
    status: 200
  });
});