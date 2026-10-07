using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class TextPosition : MonoBehaviour {
	public RectTransform rect;
	public float xPos = 0.15f;
	public float yPos = 0.95f;
	// Use this for initialization
	void Start () {
		rect.position = new Vector3 (Screen.width*xPos, Screen.height*yPos, 0);
		Destroy (this);
	}

}
