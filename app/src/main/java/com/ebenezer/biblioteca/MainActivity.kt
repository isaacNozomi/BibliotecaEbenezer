package com.ebenezer.biblioteca

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.ebenezer.biblioteca.data.ParrafoEntity

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme {
                BibliotecaEbenezerApp()
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun BibliotecaEbenezerApp(viewModel: LibraryViewModel = viewModel()) {
    var showBooks by remember { mutableStateOf(true) }
    var selectedBookTitle by remember { mutableStateOf("") }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(if (showBooks) "Biblioteca Ebenezer" else selectedBookTitle.take(25) + "...") },
                navigationIcon = {
                    if (!showBooks) {
                        IconButton(onClick = { showBooks = true }) {
                            Icon(Icons.Default.ArrowBack, contentDescription = "Volver")
                        }
                    }
                }
            )
        }
    ) { padding ->
        if (showBooks) {
            val books by viewModel.books.collectAsState(initial = emptyList())
            LazyColumn(modifier = Modifier.padding(padding)) {
                items(books) { book ->
                    ListItem(
                        headlineContent = { Text(book.titulo, fontWeight = FontWeight.Bold) },
                        supportingContent = { Text("Código: ${book.codigo}") },
                        modifier = Modifier.clickable {
                            viewModel.selectBook(book.id)
                            selectedBookTitle = book.titulo
                            showBooks = false
                        }
                    )
                }
            }
        } else {
            val paragraphs by viewModel.paragraphs.collectAsState(initial = emptyList())
            LazyColumn(
                modifier = Modifier.padding(padding).fillMaxSize(),
                contentPadding = PaddingValues(16.dp)
            ) {
                items(paragraphs) { parrafo ->
                    ParagraphCard(parrafo)
                }
            }
        }
    }
}

@Composable
fun ParagraphCard(parrafo: ParrafoEntity) {
    Card(
        modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
        colors = CardDefaults.cardColors(
            containerColor = when(parrafo.tipo) {
                1 -> MaterialTheme.colorScheme.primaryContainer
                2 -> MaterialTheme.colorScheme.secondaryContainer.copy(alpha = 0.4f)
                else -> MaterialTheme.colorScheme.surface
            }
        )
    ) {
        Column(modifier = Modifier.padding(14.dp)) {
            when (parrafo.tipo) {
                1 -> { // ESTILO TÍTULO INTERNO
                    Text(
                        text = parrafo.contenido,
                        fontSize = 20.sp,
                        fontWeight = FontWeight.ExtraBold,
                        color = MaterialTheme.colorScheme.primary
                    )
                }
                2 -> { // ESTILO CITA BÍBLICA
                    Text(
                        text = parrafo.contenido,
                        fontSize = 16.sp,
                        fontStyle = FontStyle.Italic,
                        fontWeight = FontWeight.Medium,
                        lineHeight = 24.sp,
                        modifier = Modifier.padding(start = 8.dp)
                    )
                }
                else -> { // ESTILO NORMAL
                    Text(
                        text = parrafo.contenido,
                        fontSize = 17.sp,
                        lineHeight = 26.sp
                    )
                }
            }
            Text(
                text = parrafo.numero_parrafo.toString(),
                fontSize = 10.sp,
                modifier = Modifier.align(androidx.compose.ui.Alignment.End),
                color = MaterialTheme.colorScheme.outline
            )
        }
    }
}