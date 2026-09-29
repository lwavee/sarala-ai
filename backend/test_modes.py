import sys
import os
from typing import Optional

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.llm import LLMEngine
from core.brain import Brain, _normalize_mode

def test_normalization():
    print("--- Testing Mode Normalization ---")
    assert _normalize_mode("normal") == "normal"
    assert _normalize_mode("love") == "love"
    assert _normalize_mode("expert") == "expert"
    
    # Migrations
    assert _normalize_mode("light") == "normal"
    assert _normalize_mode("dark") == "normal"
    assert _normalize_mode("dark_blue") == "normal"
    assert _normalize_mode("dark-blue") == "normal"
    assert _normalize_mode("vedic") == "normal"
    assert _normalize_mode("developer") == "expert"
    assert _normalize_mode("dev") == "expert"
    assert _normalize_mode("partner") == "love"
    assert _normalize_mode("companion") == "love"
    assert _normalize_mode(None) == "normal"
    assert _normalize_mode("unknown_random_mode") == "normal"
    print("[OK] All normalization and backward compatibility assertions passed!")

def test_llm_personality_prompts():
    print("--- Testing LLM Personality Prompts ---")
    llm = LLMEngine()
    
    # Normal Mode
    normal_p = llm._build_personality("normal")
    assert "CORE FOUNDATION" in normal_p
    assert "NORMAL MODE" in normal_p
    assert "Everyday AI Assistant" in normal_p
    
    # Love Mode
    love_p = llm._build_personality("love")
    assert "CORE FOUNDATION" in love_p
    assert "LOVE MODE" in love_p
    assert "CRITICAL LOVE MODE RULE — FULL CAPABILITY PRESERVED" in love_p
    
    # Expert Mode
    expert_p = llm._build_personality("expert")
    assert "CORE FOUNDATION" in expert_p
    assert "EXPERT MODE" in expert_p
    assert "Deep Work & Complex Tasks" in expert_p
    
    # Legacy migration test
    migrated_p = llm._build_personality("developer")
    assert "EXPERT MODE" in migrated_p
    print("[OK] All LLM personality prompt builds verified!")

def test_brain_modes():
    print("--- Testing Brain Processing with Modes ---")
    brain = Brain()
    
    # Time query in all 3 modes
    t_normal = brain.process_input("time kya hua hai?", theme_mode="normal")
    print(f"Normal Time Reply: {t_normal}")
    assert "baj rahe hain" in t_normal
    
    t_love = brain.process_input("time kya hua hai?", theme_mode="love")
    print(f"Love Time Reply: {t_love}")
    assert "boss" in t_love
    
    t_expert = brain.process_input("time kya hua hai?", theme_mode="expert")
    print(f"Expert Time Reply: {t_expert}")
    assert "IST" in t_expert
    
    # Date query in all 3 modes
    d_normal = brain.process_input("aaj kya date hai?", theme_mode="normal")
    print(f"Normal Date Reply: {d_normal}")
    
    d_love = brain.process_input("aaj kya date hai?", theme_mode="love")
    print(f"Love Date Reply: {d_love}")
    assert "boss" in d_love
    
    d_expert = brain.process_input("aaj kya date hai?", theme_mode="expert")
    print(f"Expert Date Reply: {d_expert}")
    assert "Current Date" in d_expert

    # Greet in expert & normal
    g_expert = brain.process_input("hello", theme_mode="expert")
    print(f"Expert Greet: {g_expert}")
    assert "Expert Mode active" in g_expert
    
    g_normal = brain.process_input("hello", theme_mode="normal")
    print(f"Normal Greet: {g_normal}")
    assert "Namaste" in g_normal

    print("[OK] All Brain mode tests passed successfully!")

if __name__ == "__main__":
    test_normalization()
    test_llm_personality_prompts()
    test_brain_modes()
    print("\nALL BACKEND MODE TESTS PASSED!")
