import { Landmark, RecognitionResult } from '../types';

export function extractLandmarksVector(
  hands: { landmarks: Landmark[]; label: 'Right' | 'Left' }[]
): number[] {
  const vector = new Array(126).fill(0);
  if (!hands || hands.length === 0) return vector;

  for (const hand of hands) {
    const isRight = hand.label === 'Right';
    const offset = isRight ? 0 : 63;
    const wrist = hand.landmarks[0];

    hand.landmarks.forEach((lm, i) => {
      const idx = offset + i * 3;
      vector[idx] = lm.x - (wrist ? wrist.x : 0);
      vector[idx + 1] = lm.y - (wrist ? wrist.y : 0);
      vector[idx + 2] = lm.z - (wrist ? wrist.z : 0);
    });
  }

  return vector;
}

// 3D Euclidean distance between 2 landmarks
function dist(a: Landmark, b: Landmark): number {
  if (!a || !b) return 0;
  const dx = a.x - b.x;
  const dy = a.y - b.y;
  const dz = (a.z ?? 0) - (b.z ?? 0);
  return Math.sqrt(dx * dx + dy * dy + dz * dz);
}

// 2D distance on image plane (x, y) - robust against z-depth sensor jitter
function dist2D(a: Landmark, b: Landmark): number {
  if (!a || !b) return 0;
  const dx = a.x - b.x;
  const dy = a.y - b.y;
  return Math.sqrt(dx * dx + dy * dy);
}

export interface FingerStates {
  thumb: boolean;
  index: boolean;
  middle: boolean;
  ring: boolean;
  pinky: boolean;
  palmSize: number;
}

/**
 * Robust finger extension analyzer:
 * Uses palmSize (wrist to middle MCP) as an invariant scale ruler.
 * This guarantees the exact same detection whether the user is 30cm or 2m from the webcam.
 */
export function analyzeFingerStates(lm: Landmark[]): FingerStates {
  if (!lm || lm.length < 21) {
    return { thumb: false, index: false, middle: false, ring: false, pinky: false, palmSize: 0.1 };
  }

  const wrist = lm[0];
  const middleMcp = lm[9];
  
  // Reference unit: palm size (wrist to middle knuckle)
  const palmSize = Math.max(0.04, dist(wrist, middleMcp));

  // MCP joints: 5 (index), 9 (middle), 13 (ring), 17 (pinky)
  // PIP joints: 6, 10, 14, 18
  // TIP joints: 8, 12, 16, 20
  
  // Helper for non-thumb fingers:
  // A finger is EXTENDED if:
  // 1. Tip is further from wrist than PIP
  // 2. Tip is far from its base MCP (> 0.65 * palmSize)
  // When folded, the tip curls in towards the palm (< 0.60 * palmSize)
  const isExtended = (tipIdx: number, pipIdx: number, mcpIdx: number) => {
    const dTipWrist = dist(lm[tipIdx], wrist);
    const dPipWrist = dist(lm[pipIdx], wrist);
    const dTipMcp = dist(lm[tipIdx], lm[mcpIdx]);
    
    // Finger is considered extended if tip is pushing outward from MCP
    return dTipWrist > dPipWrist * 0.95 && dTipMcp > 0.65 * palmSize;
  };

  const indexExtended = isExtended(8, 6, 5);
  const middleExtended = isExtended(12, 10, 9);
  const ringExtended = isExtended(16, 14, 13);
  const pinkyExtended = isExtended(20, 18, 17);

  // Thumb extension (Tip 4 relative to MCP 2 and Pinky MCP 17)
  const thumbTip = lm[4];
  const thumbMcp = lm[2];
  const dThumbPinky = dist(thumbTip, lm[17]);
  const dThumbMcp = dist(thumbTip, thumbMcp);
  const thumbExtended = dThumbMcp > 0.60 * palmSize || dThumbPinky > 0.90 * palmSize;

  return {
    thumb: thumbExtended,
    index: indexExtended,
    middle: middleExtended,
    ring: ringExtended,
    pinky: pinkyExtended,
    palmSize
  };
}

export function classifyHandGesture(
  hands: { landmarks: Landmark[]; label: 'Right' | 'Left' }[]
): RecognitionResult | null {
  if (!hands || hands.length === 0) return null;

  const primaryHand = hands[0];
  const lm = primaryHand.landmarks;
  if (!lm || lm.length < 21) return null;

  const wrist = lm[0];
  const { thumb, index, middle, ring, pinky, palmSize } = analyzeFingerStates(lm);

  const thumbTip = lm[4];
  const indexTip = lm[8];
  const middleTip = lm[12];
  const ringTip = lm[16];
  const pinkyTip = lm[20];

  // Distances between fingertips for pinch / bunching
  const pinchAll = (
    dist(thumbTip, indexTip) +
    dist(thumbTip, middleTip) +
    dist(thumbTip, ringTip) +
    dist(thumbTip, pinkyTip)
  ) / palmSize;

  // =========================================================================
  // 1. "peace" (Signe V / Victoire / Paix ✌️)
  // Index et Majeur levés, Annulaire et Auriculaire repliés
  // =========================================================================
  if (index && middle && !ring && !pinky) {
    return {
      label: 'peace',
      confidence: 0.97,
      details: 'Signe de la Paix / V (Index et Majeur levés, autres pliés)'
    };
  }

  // =========================================================================
  // 2. "I" (Moi / Lettre ASL 'I' 🤙)
  // Seul l'auriculaire est levé, index et majeur repliés
  // =========================================================================
  if (pinky && !index && !middle && !ring) {
    return {
      label: 'I',
      confidence: 0.95,
      details: 'Petit doigt levé (I / Moi)'
    };
  }

  // =========================================================================
  // 3. "love" (Signe ILY 🤟)
  // Pouce, Index et Auriculaire levés, Majeur et Annulaire repliés
  // =========================================================================
  if (thumb && index && pinky && !middle && !ring) {
    return {
      label: 'love',
      confidence: 0.96,
      details: 'Signe "I Love You" (Pouce, Index, Auriculaire tendus)'
    };
  }

  // =========================================================================
  // 4. "eat" (Manger 🤌)
  // Tous les bouts des doigts réunis en corolle
  // =========================================================================
  if (pinchAll < 1.8 && (!index || !middle)) {
    return {
      label: 'eat',
      confidence: 0.93,
      details: 'Doigts regroupés en pointe vers le haut (Manger)'
    };
  }

  // =========================================================================
  // 5. "hello" (Bonjour / Main ouverte 👋)
  // Les 4 doigts principaux tendus vers le haut
  // =========================================================================
  if (index && middle && ring && pinky) {
    // Main orientée vers le haut (poignet en bas, doigts en haut)
    if (wrist.y > lm[9].y - 0.05) {
      return {
        label: 'hello',
        confidence: 0.98,
        details: 'Main ouverte levée (Bonjour / Hello)'
      };
    }
  }

  // =========================================================================
  // 6. "sleep" (Dormir 💤)
  // Main à plat inclinée sur le côté (angle horizontal prononcé)
  // =========================================================================
  if (index && middle && ring) {
    const dx = Math.abs(lm[9].x - wrist.x);
    const dy = Math.abs(lm[9].y - wrist.y);
    if (dx > dy * 0.70) {
      return {
        label: 'sleep',
        confidence: 0.92,
        details: 'Main inclinée sur le côté contre la joue (Dormir)'
      };
    }
  }

  // =========================================================================
  // 7. "hate" vs "not" (Poing avec pouce orienté 👎 / 👍)
  // Doigts repliés en poing
  // =========================================================================
  if (!index && !middle && !ring && !pinky) {
    // Si le pouce pointe nettement vers le bas
    if (thumbTip.y > wrist.y) {
      return {
        label: 'hate',
        confidence: 0.92,
        details: 'Pouce dirigé vers le bas (Haine / Pouce bas)'
      };
    } else if (thumb) {
      return {
        label: 'not',
        confidence: 0.91,
        details: 'Pouce vers l\'extérieur / levé (Non / Not)'
      };
    }
  }

  // =========================================================================
  // 8. Gestes à deux mains : Shawarma ou tacos
  // =========================================================================
  if (hands.length >= 2) {
    const w1 = hands[0].landmarks[0];
    const w2 = hands[1].landmarks[0];
    const handsDist = dist(w1, w2);

    if (handsDist < 2.0 * palmSize) {
      return {
        label: 'Shawarma',
        confidence: 0.91,
        details: 'Deux mains jointes en rouleau (Shawarma)'
      };
    } else if (handsDist < 3.5 * palmSize) {
      return {
        label: 'tacos',
        confidence: 0.89,
        details: 'Deux mains courbées face à face (Tacos)'
      };
    }
  }

  return null;
}
